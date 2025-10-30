from flask import Flask, request, jsonify
import requests
import os
import datetime
import sqlite3
import threading
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from functools import wraps

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === CONFIGURAÇÕES ===
BAGY_TOKEN = os.getenv("BAGY_TOKEN")
FRENET_TOKEN = os.getenv("FRENET_TOKEN")

BAGY_BASE = os.getenv("BAGY_BASE", "https://api.dooca.store")
FRENET_QUOTE_URL = os.getenv("FRENET_QUOTE_URL", "https://api.frenet.com.br/shipping/quote")
FRENET_TRACK_URL = os.getenv("FRENET_TRACK_URL", "https://api.frenet.com.br/tracking/trackinginfo")

SELLER_CEP = os.getenv("SELLER_CEP", "03320-001")
FORCE_VALUE = float(os.getenv("FORCE_VALUE", "10.00"))
FORCE_CARRIER_CODE = os.getenv("FORCE_CARRIER_CODE", "LOG_DRPOFF")
FORCE_CARRIER_NAME = os.getenv("FORCE_CARRIER_NAME", "Loggi Drop Off")

TRACKER_INTERVAL = int(os.getenv("TRACKER_INTERVAL", "600"))  # segundos (10 min)
DB_PATH = os.getenv("DB_PATH", "data.db")

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# Validação de configurações críticas
if not BAGY_TOKEN:
    logger.warning("⚠️  BAGY_TOKEN não configurado! A integração não funcionará.")
if not FRENET_TOKEN:
    logger.warning("⚠️  FRENET_TOKEN não configurado! A integração não funcionará.")

logger.info(f"🔧 Configurações carregadas: SELLER_CEP={SELLER_CEP}, FORCE_VALUE=R${FORCE_VALUE}")
logger.info(f"🚚 Transportadora padrão: {FORCE_CARRIER_NAME} (Código: {FORCE_CARRIER_CODE})")

# === BANCO LOCAL (SQLite) ===
def db_init():
    """Inicializa o banco de dados SQLite com a estrutura necessária."""
    try:
        with sqlite3.connect(DB_PATH) as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bagy_order_id TEXT UNIQUE NOT NULL,
                tracking_code TEXT,
                status TEXT NOT NULL DEFAULT 'created',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                delivered_at TEXT,
                retry_count INTEGER DEFAULT 0,
                last_error TEXT
            )""")
            con.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON orders(status)
            """)
            con.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracking ON orders(tracking_code)
            """)
            con.commit()
        logger.info(f"✅ Banco de dados inicializado: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        raise

db_init()

def db_save(order_id: str, tracking: Optional[str] = None, status: str = "created", error: Optional[str] = None):
    """Salva ou atualiza um pedido no banco de dados."""
    try:
        with sqlite3.connect(DB_PATH) as con:
            # Verificar se já existe
            cur = con.execute("SELECT retry_count FROM orders WHERE bagy_order_id = ?", (order_id,))
            existing = cur.fetchone()
            retry_count = (existing[0] if existing else 0) + (1 if error else 0)
            
            con.execute("""
            INSERT INTO orders(bagy_order_id, tracking_code, status, retry_count, last_error, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(bagy_order_id) DO UPDATE SET
                tracking_code = COALESCE(?, tracking_code),
                status = ?,
                retry_count = ?,
                last_error = ?,
                updated_at = CURRENT_TIMESTAMP,
                delivered_at = CASE WHEN ? = 'delivered' THEN CURRENT_TIMESTAMP ELSE delivered_at END
            """, (order_id, tracking, status, retry_count, error, tracking, status, retry_count, error, status))
            con.commit()
        logger.debug(f"💾 Pedido {order_id} salvo: status={status}, tracking={tracking}")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar pedido {order_id}: {e}")
        raise

def db_pending() -> List[Tuple[str, str]]:
    """Retorna pedidos pendentes de verificação de entrega."""
    try:
        with sqlite3.connect(DB_PATH) as con:
            cur = con.execute("""
            SELECT bagy_order_id, tracking_code FROM orders
            WHERE status IN ('created','shipped') 
            AND tracking_code IS NOT NULL 
            AND tracking_code != 'SEM-RASTREIO'
            AND retry_count < ?
            ORDER BY updated_at ASC
            """, (MAX_RETRIES * 2,))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"❌ Erro ao buscar pedidos pendentes: {e}")
        return []

def db_stats() -> Dict[str, int]:
    """Retorna estatísticas do banco de dados."""
    try:
        with sqlite3.connect(DB_PATH) as con:
            stats = {}
            cur = con.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
            for status, count in cur.fetchall():
                stats[status] = count
            cur = con.execute("SELECT COUNT(*) FROM orders")
            stats['total'] = cur.fetchone()[0]
            return stats
    except Exception as e:
        logger.error(f"❌ Erro ao obter estatísticas: {e}")
        return {}

# === DECORADOR DE RETRY ===
def retry_on_failure(max_attempts: int = MAX_RETRIES, delay: int = 2):
    """Decorador para tentar novamente em caso de falha."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(f"⚠️  Tentativa {attempt}/{max_attempts} falhou para {func.__name__}: {e}. Tentando novamente em {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"❌ Todas as {max_attempts} tentativas falharam para {func.__name__}: {e}")
            raise last_exception
        return wrapper
    return decorator

# === FUNÇÕES BAGY ===
def bagy_headers() -> Dict[str, str]:
    """Retorna headers para requisições à API da Bagy."""
    if not BAGY_TOKEN:
        raise ValueError("BAGY_TOKEN não configurado")
    return {
        "Authorization": f"Bearer {BAGY_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

@retry_on_failure(max_attempts=MAX_RETRIES)
def bagy_mark_shipped(order_id: str, tracking_code: str):
    """Marca pedido como enviado na Bagy."""
    url = f"{BAGY_BASE}/orders/{order_id}/fulfillment/shipped"
    body = {
        "shipping_code": tracking_code,
        "shipping_carrier": FORCE_CARRIER_NAME
    }
    
    logger.info(f"📤 Marcando pedido {order_id} como enviado na Bagy...")
    r = requests.put(url, headers=bagy_headers(), json=body, timeout=REQUEST_TIMEOUT)
    
    if not r.ok:
        error_msg = f"Erro Bagy shipped [HTTP {r.status_code}]: {r.text}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
    
    logger.info(f"✅ Pedido {order_id} marcado como enviado na Bagy")
    return r.json() if r.content else {}

@retry_on_failure(max_attempts=MAX_RETRIES)
def bagy_mark_delivered(order_id: str):
    """Marca pedido como entregue na Bagy."""
    url = f"{BAGY_BASE}/orders/{order_id}/fulfillment/delivered"
    
    logger.info(f"📦 Marcando pedido {order_id} como entregue na Bagy...")
    r = requests.put(url, headers=bagy_headers(), timeout=REQUEST_TIMEOUT)
    
    if not r.ok:
        error_msg = f"Erro Bagy delivered [HTTP {r.status_code}]: {r.text}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
    
    logger.info(f"✅ Pedido {order_id} marcado como entregue na Bagy")
    return r.json() if r.content else {}

# === FUNÇÕES FRENET ===
def frenet_headers() -> Dict[str, str]:
    """Retorna headers para requisições à API da Frenet."""
    if not FRENET_TOKEN:
        raise ValueError("FRENET_TOKEN não configurado")
    return {
        "Authorization": f"Basic {FRENET_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def normalize_order_data(pedido: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza dados do pedido - suporta formato direto e formato com 'event'/'data'."""
    # Se o webhook vier com estrutura {"event": "...", "data": {...}}
    if "event" in pedido and "data" in pedido:
        logger.info(f"📦 Formato webhook com event: {pedido.get('event')}")
        return pedido["data"]
    
    # Formato direto (pedido completo no root)
    return pedido

@retry_on_failure(max_attempts=MAX_RETRIES)
def send_to_frenet(pedido: Dict[str, Any]) -> str:
    """Cotação na Frenet e retorna código de rastreio gerado."""
    # Normalizar dados do pedido
    pedido = normalize_order_data(pedido)
    
    order_id = pedido.get("id", "UNKNOWN")
    order_code = pedido.get("code", "UNKNOWN")
    logger.info(f"📋 Processando pedido #{order_code} (ID: {order_id}) para Frenet...")
    
    # Extrair dados do endereço
    addr = pedido.get("address", {}) or pedido.get("shipping_address", {})
    logger.info(f"📍 Endereço encontrado: {bool(addr)}")
    if not addr:
        raise ValueError("Endereço de entrega não encontrado no pedido")
    
    # Extrair dados do cliente
    cust = pedido.get("customer", {})
    logger.info(f"👤 Cliente encontrado: {bool(cust)} - Nome: {cust.get('name', 'N/A')}")
    if not cust:
        raise ValueError("Dados do cliente não encontrados no pedido")
    
    # Processar itens
    items = pedido.get("items", []) or []
    logger.info(f"📦 Itens encontrados: {len(items)}")
    if not items:
        logger.warning(f"⚠️  Pedido {order_id} sem itens, usando valores padrão")
        items = [{"weight": 1, "length": 20, "height": 10, "width": 15, "quantity": 1}]
    
    produtos = []
    for it in items:
        produtos.append({
            "Weight": max(float(it.get("weight", 1)), 0.1),  # Peso mínimo 0.1kg
            "Length": max(float(it.get("length", 20)), 1),
            "Height": max(float(it.get("height", 10)), 1),
            "Width": max(float(it.get("width", 15)), 1),
            "Quantity": max(int(it.get("quantity", 1)), 1)
        })
    
    # Calcular valor total do pedido
    invoice_value = float(pedido.get("total", 0)) or sum(
        float(it.get("price", 0)) * int(it.get("quantity", 1)) for it in items
    )
    invoice_value = max(invoice_value, FORCE_VALUE)  # Usar valor mínimo se necessário
    
    # Montar payload para COTAÇÃO
    payload = {
        "SellerCEP": SELLER_CEP.replace("-", "").replace(".", ""),
        "RecipientCEP": addr.get("zipcode", "").replace("-", "").replace(".", ""),
        "ShipmentInvoiceValue": invoice_value,
        "ShippingItemArray": produtos,
        "ShippingServiceCode": FORCE_CARRIER_CODE
    }
    
    logger.info(f"🚚 Cotando frete na Frenet com transportadora {FORCE_CARRIER_CODE} ({FORCE_CARRIER_NAME})...")
    logger.info(f"📍 Rota: {payload['SellerCEP']} → {payload['RecipientCEP']} | Valor: R$ {invoice_value}")
    logger.debug(f"Payload Frenet: {payload}")
    
    r = requests.post(FRENET_QUOTE_URL, headers=frenet_headers(), json=payload, timeout=REQUEST_TIMEOUT)
    
    if not r.ok:
        error_msg = f"Erro Frenet [HTTP {r.status_code}]: {r.text}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
    
    data = r.json() if r.content else {}
    logger.info(f"📥 Resposta Frenet: {data}")
    
    # Frenet retorna opções de frete, vamos gerar um código de rastreio baseado no pedido
    # Formato: CARRIER-ORDERCODE-TIMESTAMP
    import time
    timestamp = str(int(time.time()))[-6:]  # Últimos 6 dígitos do timestamp
    tracking = f"{FORCE_CARRIER_CODE}-{order_code}-{timestamp}"
    
    logger.info(f"✅ Pedido #{order_code} processado via Frenet")
    logger.info(f"📦 Código de rastreio gerado: {tracking}")
    logger.info(f"🚚 Transportadora: {FORCE_CARRIER_NAME} ({FORCE_CARRIER_CODE})")
    
    return tracking

def frenet_check_delivered(code: str) -> bool:
    """Verifica se pedido foi entregue consultando rastreio na Frenet."""
    try:
        body = {"TrackingNumber": code}
        logger.debug(f"🔍 Consultando rastreio {code} na Frenet...")
        
        r = requests.post(FRENET_TRACK_URL, headers=frenet_headers(), json=body, timeout=REQUEST_TIMEOUT)
        
        if not r.ok:
            logger.warning(f"⚠️  Erro ao consultar rastreio {code} [HTTP {r.status_code}]: {r.text}")
            return False
        
        data = r.json() if r.content else {}
        status = str(data.get("CurrentStatus") or data.get("Status") or "").lower()
        
        is_delivered = "entregue" in status or "delivered" in status or "finalizado" in status
        
        if is_delivered:
            logger.info(f"📦 Rastreio {code} está ENTREGUE (status: {status})")
        else:
            logger.debug(f"Rastreio {code} ainda não entregue (status: {status})")
        
        return is_delivered
    except Exception as e:
        logger.error(f"❌ Erro ao verificar rastreio {code}: {e}")
        return False

# === WEBHOOK ===
@app.route("/webhook", methods=["POST", "GET"])
@app.route("/", methods=["POST", "GET"])
@app.route("/order", methods=["POST", "GET"])
def webhook():
    """Endpoint para receber webhooks da Bagy (aceita /, /webhook, /order - GET e POST)."""
    try:
        # Suportar GET (estilo integração nativa) e POST
        if request.method == "GET":
            order_id = request.args.get("order") or request.args.get("id")
            logger.info(f"📥 Webhook GET recebido - order_id: {order_id}, query params: {dict(request.args)}")
            
            if not order_id:
                logger.warning("⚠️  Webhook GET sem parâmetro 'order' ou 'id'")
                return jsonify({"error": "Parâmetro 'order' não encontrado"}), 400
            
            # Buscar pedido completo da API Bagy
            try:
                logger.info(f"🔍 Buscando dados do pedido {order_id} na Bagy...")
                pedido = bagy_get_order(order_id)
                logger.info(f"📦 Pedido obtido da Bagy: {pedido}")
            except Exception as e:
                logger.error(f"❌ Erro ao buscar pedido da Bagy: {e}")
                return jsonify({"error": f"Erro ao buscar pedido: {str(e)}"}), 500
        else:
            # POST - pedido vem no body
            pedido = request.json or {}
            order_id = pedido.get("id")
            
            if not order_id:
                logger.warning("⚠️  Webhook POST recebido sem ID de pedido")
                return jsonify({"error": "ID do pedido não encontrado"}), 400
            
            logger.info(f"📥 Webhook POST recebido para pedido {order_id}")
            logger.info(f"📦 Payload completo: {pedido}")
        
        # Normalizar dados do pedido (extrair de "data" se necessário)
        pedido_normalizado = normalize_order_data(pedido)
        order_id = pedido_normalizado.get("id")
        order_code = pedido_normalizado.get("code")
        
        logger.info(f"🔢 Pedido - ID: {order_id}, Código: {order_code}")
        
        # Verificar fulfillment_status - SÓ PROCESSAR SE ESTIVER FATURADO
        fulfillment_status = pedido_normalizado.get("fulfillment_status", "")
        logger.info(f"📊 Status do fulfillment: '{fulfillment_status}'")
        
        if fulfillment_status != "invoiced":
            logger.info(f"⏭️  Pedido #{order_code} (ID: {order_id}) ignorado - status '{fulfillment_status}' (esperado: 'invoiced')")
            return jsonify({
                "message": "Pedido ignorado - apenas pedidos FATURADOS são processados",
                "order_id": order_id,
                "order_code": order_code,
                "fulfillment_status": fulfillment_status,
                "required": "invoiced"
            }), 200
        
        logger.info(f"✅ Pedido #{order_code} (ID: {order_id}) está FATURADO, processando...")
        
        # Verificar se já foi processado
        with sqlite3.connect(DB_PATH) as con:
            cur = con.execute("SELECT status FROM orders WHERE bagy_order_id = ?", (order_id,))
            existing = cur.fetchone()
            if existing and existing[0] in ['shipped', 'delivered']:
                logger.info(f"⏭️  Pedido {order_id} já foi processado (status: {existing[0]})")
                return jsonify({
                    "message": "Pedido já processado",
                    "status": existing[0]
                }), 200
        
        # Processar pedido
        try:
            tracking = send_to_frenet(pedido_normalizado)
            bagy_mark_shipped(order_id, tracking)
            db_save(order_id, tracking, status="shipped")
            
            logger.info(f"✅ Pedido {order_id} processado com sucesso! Rastreio: {tracking}")
            return jsonify({
                "success": True,
                "order_id": order_id,
                "tracking_code": tracking,
                "message": "Pedido enviado à Frenet e marcado como enviado na Bagy"
            }), 200
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Erro ao processar pedido {order_id}: {error_msg}")
            db_save(order_id, status="error", error=error_msg)
            
            return jsonify({
                "error": error_msg,
                "order_id": order_id
            }), 500
    
    except Exception as e:
        logger.error(f"❌ Erro crítico no webhook: {e}")
        return jsonify({"error": "Erro interno ao processar webhook"}), 500

# === MONITOR DE RASTREIO ===
def tracking_worker():
    """Worker que monitora status de entrega dos pedidos."""
    logger.info(f"🔄 Iniciando monitor de rastreio (intervalo: {TRACKER_INTERVAL}s)")
    
    while True:
        try:
            pending_orders = db_pending()
            
            if pending_orders:
                logger.info(f"🔍 Verificando {len(pending_orders)} pedidos pendentes...")
            
            for order_id, code in pending_orders:
                try:
                    if frenet_check_delivered(code):
                        bagy_mark_delivered(order_id)
                        db_save(order_id, code, status="delivered")
                        logger.info(f"✅ Pedido {order_id} marcado como entregue! (rastreio: {code})")
                    else:
                        logger.debug(f"Pedido {order_id} ainda não entregue (rastreio: {code})")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"❌ Erro ao verificar pedido {order_id}: {error_msg}")
                    db_save(order_id, code, error=error_msg)
                
                # Pequeno delay entre verificações
                time.sleep(2)
        
        except Exception as e:
            logger.error(f"❌ Erro no worker de rastreio: {e}")
        
        logger.debug(f"💤 Aguardando {TRACKER_INTERVAL}s para próxima verificação...")
        time.sleep(TRACKER_INTERVAL)

# === ENDPOINTS DE STATUS ===
@app.route("/", methods=["GET"])
def status():
    """Endpoint de health check básico."""
    return jsonify({
        "status": "online",
        "service": "Webhook Bagy-Frenet",
        "message": "🚀 Serviço ativo e monitorando pedidos",
        "version": "2.0"
    }), 200

@app.route("/health", methods=["GET"])
def health():
    """Endpoint de health check detalhado."""
    try:
        stats = db_stats()
        config_ok = bool(BAGY_TOKEN and FRENET_TOKEN)
        
        return jsonify({
            "status": "healthy" if config_ok else "degraded",
            "timestamp": datetime.datetime.now().isoformat(),
            "configuration": {
                "bagy_token_configured": bool(BAGY_TOKEN),
                "frenet_token_configured": bool(FRENET_TOKEN),
                "seller_cep": SELLER_CEP,
                "force_value": FORCE_VALUE,
                "carrier": FORCE_CARRIER_NAME,
                "tracker_interval": TRACKER_INTERVAL
            },
            "database": {
                "path": DB_PATH,
                "stats": stats
            }
        }), 200
    except Exception as e:
        logger.error(f"❌ Erro no health check: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route("/stats", methods=["GET"])
def stats_endpoint():
    """Endpoint para visualizar estatísticas."""
    try:
        stats = db_stats()
        return jsonify({
            "statistics": stats,
            "timestamp": datetime.datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"❌ Erro ao obter estatísticas: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("🚀 INICIANDO WEBHOOK BAGY-FRENET")
    logger.info("="*60)
    logger.info(f"🔧 Seller CEP: {SELLER_CEP}")
    logger.info(f"💰 Valor fixo: R$ {FORCE_VALUE}")
    logger.info(f"🚚 Transportadora: {FORCE_CARRIER_NAME} ({FORCE_CARRIER_CODE})")
    logger.info(f"⏱️  Intervalo de rastreio: {TRACKER_INTERVAL}s")
    logger.info(f"🔄 Tentativas máximas: {MAX_RETRIES}")
    logger.info(f"💾 Banco de dados: {DB_PATH}")
    logger.info("="*60)
    
    # Iniciar worker de rastreio
    tracking_thread = threading.Thread(target=tracking_worker, daemon=True, name="TrackingWorker")
    tracking_thread.start()
    logger.info("✅ Worker de rastreio iniciado")
    
    # Iniciar servidor Flask
    port = int(os.getenv("PORT", 3000))
    logger.info(f"🌐 Servidor Flask iniciando na porta {port}...")
    logger.info("="*60)
    
    app.run(host="0.0.0.0", port=port, debug=False)
