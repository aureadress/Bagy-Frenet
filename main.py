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

# URLs da API de envio (configurável)
SHIPPING_API_URL = os.getenv("SHIPPING_API_URL", "https://api.frenet.com.br/shipping/quote")
TRACKING_API_URL = os.getenv("TRACKING_API_URL", "https://api.frenet.com.br/tracking/trackinginfo")

# Compatibilidade com nomes antigos
FRENET_QUOTE_URL = SHIPPING_API_URL
FRENET_TRACK_URL = TRACKING_API_URL

SELLER_CEP = os.getenv("SELLER_CEP", "03320-001")
FORCE_VALUE = float(os.getenv("FORCE_VALUE", "10.00"))
FORCE_CARRIER_CODE = os.getenv("FORCE_CARRIER_CODE", "LOG_DRPOFF")
FORCE_CARRIER_NAME = os.getenv("FORCE_CARRIER_NAME", "Loggi Drop Off")

# Tipo de integração: "frenet", "loggi", "kangu", "custom"
INTEGRATION_TYPE = os.getenv("INTEGRATION_TYPE", "frenet")

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
logger.info(f"🔗 Tipo de integração: {INTEGRATION_TYPE.upper()}")
logger.info(f"🌐 API de envio: {SHIPPING_API_URL}")

# === BANCO LOCAL (SQLite) ===
def db_init():
    """Inicializa o banco de dados SQLite com a estrutura necessária."""
    try:
        with sqlite3.connect(DB_PATH) as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bagy_order_id TEXT UNIQUE NOT NULL,
                bagy_order_code TEXT,
                tracking_code TEXT,
                status TEXT NOT NULL DEFAULT 'created',
                customer_name TEXT,
                customer_cpf TEXT,
                customer_email TEXT,
                customer_phone TEXT,
                address_zipcode TEXT,
                address_street TEXT,
                address_number TEXT,
                address_complement TEXT,
                address_neighborhood TEXT,
                address_city TEXT,
                address_state TEXT,
                total_value REAL,
                shipping_cost REAL,
                order_data_json TEXT,
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
            con.execute("""
            CREATE INDEX IF NOT EXISTS idx_order_code ON orders(bagy_order_code)
            """)
            con.commit()
        logger.info(f"✅ Banco de dados inicializado: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        raise

db_init()

def db_save(order_id: str, tracking: Optional[str] = None, status: str = "created", error: Optional[str] = None, order_data: Optional[Dict[str, Any]] = None):
    """Salva ou atualiza um pedido no banco de dados."""
    import json
    try:
        with sqlite3.connect(DB_PATH) as con:
            # Verificar se já existe
            cur = con.execute("SELECT retry_count FROM orders WHERE bagy_order_id = ?", (order_id,))
            existing = cur.fetchone()
            retry_count = (existing[0] if existing else 0) + (1 if error else 0)
            
            # Se order_data foi fornecido, extrair campos individuais
            if order_data:
                order_code = order_data.get("order_code")
                customer = order_data.get("customer", {})
                address = order_data.get("address", {})
                total_value = order_data.get("total_value", 0)
                shipping_cost = order_data.get("shipping_cost", 0)
                order_json = json.dumps(order_data, ensure_ascii=False)
            else:
                order_code = None
                customer = {}
                address = {}
                total_value = 0
                shipping_cost = 0
                order_json = None
            
            if order_data:
                # INSERT com dados completos
                con.execute("""
                INSERT INTO orders(
                    bagy_order_id, bagy_order_code, tracking_code, status,
                    customer_name, customer_cpf, customer_email, customer_phone,
                    address_zipcode, address_street, address_number, address_complement,
                    address_neighborhood, address_city, address_state,
                    total_value, shipping_cost, order_data_json,
                    retry_count, last_error, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bagy_order_id) DO UPDATE SET
                    bagy_order_code = COALESCE(?, bagy_order_code),
                    tracking_code = COALESCE(?, tracking_code),
                    status = ?,
                    customer_name = COALESCE(?, customer_name),
                    customer_cpf = COALESCE(?, customer_cpf),
                    customer_email = COALESCE(?, customer_email),
                    customer_phone = COALESCE(?, customer_phone),
                    address_zipcode = COALESCE(?, address_zipcode),
                    address_street = COALESCE(?, address_street),
                    address_number = COALESCE(?, address_number),
                    address_complement = COALESCE(?, address_complement),
                    address_neighborhood = COALESCE(?, address_neighborhood),
                    address_city = COALESCE(?, address_city),
                    address_state = COALESCE(?, address_state),
                    total_value = COALESCE(?, total_value),
                    shipping_cost = COALESCE(?, shipping_cost),
                    order_data_json = COALESCE(?, order_data_json),
                    retry_count = ?,
                    last_error = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    delivered_at = CASE WHEN ? = 'delivered' THEN CURRENT_TIMESTAMP ELSE delivered_at END
                """, (
                    # INSERT values
                    order_id, order_code, tracking, status,
                    customer.get("name"), customer.get("cpf"), customer.get("email"), customer.get("phone"),
                    address.get("zipcode"), address.get("street"), address.get("number"), address.get("complement"),
                    address.get("neighborhood"), address.get("city"), address.get("state"),
                    total_value, shipping_cost, order_json,
                    retry_count, error,
                    # UPDATE values
                    order_code, tracking, status,
                    customer.get("name"), customer.get("cpf"), customer.get("email"), customer.get("phone"),
                    address.get("zipcode"), address.get("street"), address.get("number"), address.get("complement"),
                    address.get("neighborhood"), address.get("city"), address.get("state"),
                    total_value, shipping_cost, order_json,
                    retry_count, error, status
                ))
            else:
                # INSERT simples (compatibilidade com código existente)
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
def shipping_api_headers() -> Dict[str, str]:
    """Retorna headers para requisições à API de envio (configurável por tipo)."""
    if not FRENET_TOKEN:
        raise ValueError("FRENET_TOKEN não configurado")
    
    # Headers específicos por tipo de integração
    if INTEGRATION_TYPE == "loggi":
        return {
            "Authorization": f"Bearer {FRENET_TOKEN}",
            "Content-Type": "application/json"
        }
    elif INTEGRATION_TYPE == "kangu":
        return {
            "token": FRENET_TOKEN,
            "Content-Type": "application/json"
        }
    else:  # frenet ou custom
        return {
            "Authorization": f"Basic {FRENET_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

# Alias para compatibilidade
def frenet_headers() -> Dict[str, str]:
    """Alias para shipping_api_headers() - compatibilidade."""
    return shipping_api_headers()

def normalize_order_data(pedido: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza dados do pedido - suporta formato direto e formato com 'event'/'data'."""
    # Se o webhook vier com estrutura {"event": "...", "data": {...}}
    if "event" in pedido and "data" in pedido:
        logger.info(f"📦 Formato webhook com event: {pedido.get('event')}")
        return pedido["data"]
    
    # Formato direto (pedido completo no root)
    return pedido

@retry_on_failure(max_attempts=MAX_RETRIES)
def send_to_frenet_shipments(pedido: Dict[str, Any]) -> Dict[str, Any]:
    """Envia pedido para API de Shipments da Frenet (cria pedido no painel 'Gerencie suas etiquetas')."""
    # Normalizar dados do pedido
    pedido = normalize_order_data(pedido)
    
    order_id = pedido.get("id", "UNKNOWN")
    order_code = pedido.get("code", "UNKNOWN")
    logger.info(f"📋 Enviando pedido #{order_code} (ID: {order_id}) para Frenet...")
    
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
    
    # Calcular peso total e dimensões
    total_weight = sum(float(it.get("weight", 500)) for it in items) / 1000  # Converter gramas para kg
    total_weight = max(total_weight, 0.1)  # Mínimo 0.1kg
    
    # Calcular valor total
    invoice_value = float(pedido.get("total", 0)) or sum(
        float(it.get("price", 0)) * int(it.get("quantity", 1)) for it in items
    )
    
    # Limpar e formatar dados
    recipient_zipcode = addr.get("zipcode", "").replace("-", "").replace(".", "").strip()
    recipient_name = cust.get("name", "Cliente")
    recipient_phone = cust.get("phone", "").replace("(", "").replace(")", "").replace("-", "").replace(" ", "").strip()
    recipient_email = cust.get("email", "")
    recipient_cpf = cust.get("cpf", cust.get("document", "")).replace(".", "").replace("-", "").strip()
    
    # Montar payload para API Frenet Shipments
    # Baseado na documentação: https://docs.frenet.com.br/docs/shipments-whitelabel
    payload = {
        "OrderNumber": str(order_code),  # Número do pedido na sua plataforma
        "RecipientDocument": recipient_cpf if recipient_cpf else "",  # CPF do destinatário
        "RecipientName": recipient_name,
        "RecipientEmail": recipient_email,
        "RecipientPhone": recipient_phone,
        "RecipientZipCode": recipient_zipcode,
        "RecipientAddress": addr.get("street", addr.get("address", "")),
        "RecipientAddressNumber": addr.get("number", "S/N"),
        "RecipientAddressComplement": addr.get("complement", ""),
        "RecipientAddressDistrict": addr.get("district", addr.get("neighborhood", "")),
        "RecipientCity": addr.get("city", ""),
        "RecipientState": addr.get("state", ""),
        "RecipientCountry": "BR",
        "PackageHeight": 10,  # cm - ajustar conforme necessário
        "PackageWidth": 15,   # cm
        "PackageLength": 20,  # cm
        "PackageWeight": total_weight,  # kg
        "InvoiceValue": invoice_value,
        "ShippingQuoteValue": float(pedido.get("shipping_cost", FORCE_VALUE)),
        "Items": [
            {
                "SKU": it.get("sku", f"ITEM-{idx}"),
                "Description": it.get("name", "Produto"),
                "Quantity": int(it.get("quantity", 1)),
                "Price": float(it.get("price", 0))
            }
            for idx, it in enumerate(items, 1)
        ]
    }
    
    logger.info(f"📤 Enviando para Frenet Shipments API...")
    logger.info(f"📍 Origem: {SELLER_CEP} → Destino: {recipient_zipcode}")
    logger.info(f"💰 Valor: R$ {invoice_value} | Peso: {total_weight}kg")
    logger.info(f"👤 Cliente: {recipient_name} | Pedido: {order_code}")
    logger.debug(f"Payload Frenet: {payload}")
    
    # URL da API de Shipments (pode variar - verificar documentação)
    shipments_url = os.getenv("FRENET_SHIPMENTS_URL", "https://api.frenet.com.br/v1/shipments")
    
    r = requests.post(shipments_url, headers=frenet_headers(), json=payload, timeout=REQUEST_TIMEOUT)
    
    if not r.ok:
        error_msg = f"Erro Frenet Shipments [HTTP {r.status_code}]: {r.text}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
    
    response_data = r.json() if r.content else {}
    logger.info(f"📥 Resposta Frenet: {response_data}")
    
    # Extrair ID do pedido criado na Frenet
    frenet_order_id = response_data.get("OrderId") or response_data.get("order_id") or response_data.get("id")
    
    logger.info(f"✅ Pedido #{order_code} criado na Frenet com sucesso!")
    if frenet_order_id:
        logger.info(f"🆔 ID Frenet: {frenet_order_id}")
    logger.info(f"👉 Acesse painel.frenet.com.br → Gerencie suas etiquetas")
    logger.info(f"🏷️  O pedido deve aparecer lá para você gerar a etiqueta manualmente")
    
    # Retornar dados estruturados
    order_data = {
        "order_id": order_id,
        "order_code": order_code,
        "frenet_order_id": frenet_order_id,
        "customer": {
            "name": recipient_name,
            "cpf": recipient_cpf,
            "email": recipient_email,
            "phone": recipient_phone
        },
        "address": {
            "zipcode": recipient_zipcode,
            "street": addr.get("street", addr.get("address", "")),
            "number": addr.get("number", "S/N"),
            "complement": addr.get("complement", ""),
            "neighborhood": addr.get("district", addr.get("neighborhood", "")),
            "city": addr.get("city", ""),
            "state": addr.get("state", "")
        },
        "items": [
            {
                "name": it.get("name", "Produto"),
                "quantity": it.get("quantity", 1),
                "weight": it.get("weight", 500),
                "price": it.get("price", 0)
            }
            for it in items
        ],
        "total_value": invoice_value,
        "shipping_cost": float(pedido.get("shipping_cost", 0)),
        "frenet_response": response_data
    }
    
    return order_data

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
            
            # Normalizar PRIMEIRO para extrair o ID correto
            pedido_temp = normalize_order_data(pedido)
            order_id = pedido_temp.get("id")
            order_code = pedido_temp.get("code")
            
            if not order_id:
                logger.warning("⚠️  Webhook POST recebido sem ID de pedido")
                logger.warning(f"📦 Payload recebido: {pedido}")
                return jsonify({"error": "ID do pedido não encontrado"}), 400
            
            logger.info(f"📥 Webhook POST recebido para pedido {order_id} (código: {order_code})")
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
        
        # Processar pedido - ENVIAR PARA FRENET SHIPMENTS API
        try:
            order_data = send_to_frenet_shipments(pedido_normalizado)
            
            # Salvar no banco como "pending" (aguardando você gerar etiqueta manualmente na Frenet)
            db_save(order_id, tracking=None, status="pending", order_data=order_data)
            
            logger.info(f"✅ Pedido #{order_code} (ID: {order_id}) enviado para Frenet com sucesso!")
            logger.info(f"🏷️  Pedido deve aparecer em: painel.frenet.com.br → Gerencie suas etiquetas")
            logger.info(f"👉 Acesse lá para escolher transportadora e gerar a etiqueta")
            
            return jsonify({
                "success": True,
                "order_id": order_id,
                "order_code": order_code,
                "frenet_order_id": order_data.get("frenet_order_id"),
                "message": "Pedido criado na Frenet! Acesse o painel para gerar etiqueta.",
                "order_data": order_data,
                "next_steps": [
                    "1. Acesse https://painel.frenet.com.br",
                    "2. Vá em 'Gerencie suas etiquetas'",
                    "3. Encontre o pedido #" + str(order_code),
                    "4. Escolha a transportadora (recomendado: Loggi Drop Off)",
                    "5. Gere a etiqueta e imprima",
                    "6. Faça a postagem do pacote",
                    "7. O sistema vai monitorar o rastreio e atualizar a Bagy quando entregue"
                ]
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
    """
    Worker que monitora status de entrega dos pedidos.
    
    IMPORTANTE: Este worker só funciona DEPOIS que você:
    1. Gerar a etiqueta manualmente na Frenet
    2. Fazer a postagem física
    3. Adicionar o código de rastreio no banco de dados
    
    O worker verifica periodicamente se o pedido foi entregue e atualiza a Bagy automaticamente.
    """
    logger.info(f"🔄 Iniciando monitor de rastreio (intervalo: {TRACKER_INTERVAL}s)")
    logger.info(f"📋 Este worker aguarda você adicionar códigos de rastreio manualmente")
    
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

@app.route("/orders", methods=["GET"])
def orders_list():
    """Endpoint para visualizar pedidos salvos."""
    import json
    try:
        status_filter = request.args.get("status", "pending")
        
        with sqlite3.connect(DB_PATH) as con:
            con.row_factory = sqlite3.Row
            query = """
                SELECT * FROM orders 
                WHERE status = ? OR ? = 'all'
                ORDER BY created_at DESC
                LIMIT 100
            """
            cur = con.execute(query, (status_filter, status_filter))
            rows = cur.fetchall()
            
            orders = []
            for row in rows:
                order = dict(row)
                # Parse JSON data if available
                if order.get("order_data_json"):
                    try:
                        order["parsed_data"] = json.loads(order["order_data_json"])
                    except:
                        order["parsed_data"] = None
                orders.append(order)
        
        # Formato HTML para visualização fácil
        if request.args.get("format") != "json":
            html = """
            <!DOCTYPE html>
            <html lang="pt-BR">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pedidos Bagy - Frenet</title>
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: #f5f7fa;
                        padding: 20px;
                    }
                    .container { max-width: 1400px; margin: 0 auto; }
                    .header {
                        background: white;
                        padding: 30px;
                        border-radius: 10px;
                        margin-bottom: 20px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    h1 { color: #2c3e50; margin-bottom: 10px; }
                    .filters {
                        display: flex;
                        gap: 10px;
                        margin-top: 20px;
                    }
                    .filter-btn {
                        padding: 10px 20px;
                        border: 2px solid #3498db;
                        background: white;
                        color: #3498db;
                        border-radius: 5px;
                        cursor: pointer;
                        text-decoration: none;
                        transition: all 0.3s;
                    }
                    .filter-btn:hover, .filter-btn.active {
                        background: #3498db;
                        color: white;
                    }
                    .order-card {
                        background: white;
                        padding: 25px;
                        border-radius: 10px;
                        margin-bottom: 15px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    .order-header {
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 20px;
                        padding-bottom: 15px;
                        border-bottom: 2px solid #ecf0f1;
                    }
                    .order-id {
                        font-size: 20px;
                        font-weight: bold;
                        color: #2c3e50;
                    }
                    .status {
                        padding: 8px 15px;
                        border-radius: 20px;
                        font-size: 14px;
                        font-weight: 600;
                    }
                    .status-pending { background: #fff3cd; color: #856404; }
                    .status-shipped { background: #d1ecf1; color: #0c5460; }
                    .status-delivered { background: #d4edda; color: #155724; }
                    .status-error { background: #f8d7da; color: #721c24; }
                    .order-info {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                        gap: 20px;
                    }
                    .info-section {
                        padding: 15px;
                        background: #f8f9fa;
                        border-radius: 8px;
                    }
                    .info-title {
                        font-weight: 600;
                        color: #495057;
                        margin-bottom: 10px;
                        font-size: 14px;
                        text-transform: uppercase;
                    }
                    .info-content {
                        color: #212529;
                        line-height: 1.6;
                    }
                    .info-content strong {
                        display: inline-block;
                        width: 100px;
                        color: #6c757d;
                    }
                    .copy-btn {
                        background: #28a745;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 5px;
                        cursor: pointer;
                        margin-top: 10px;
                    }
                    .copy-btn:hover { background: #218838; }
                    .empty-state {
                        text-align: center;
                        padding: 60px 20px;
                        background: white;
                        border-radius: 10px;
                        color: #6c757d;
                    }
                    .empty-state i { font-size: 64px; margin-bottom: 20px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📦 Pedidos Bagy → Frenet</h1>
                        <p style="color: #6c757d; margin-top: 10px;">
                            Visualize e copie os dados dos pedidos para criar etiquetas na Frenet
                        </p>
                        <div class="filters">
                            <a href="/orders?status=pending" class="filter-btn {pending_active}">⏳ Pendentes</a>
                            <a href="/orders?status=shipped" class="filter-btn {shipped_active}">📮 Enviados</a>
                            <a href="/orders?status=delivered" class="filter-btn {delivered_active}">✅ Entregues</a>
                            <a href="/orders?status=error" class="filter-btn {error_active}">❌ Erros</a>
                            <a href="/orders?status=all" class="filter-btn {all_active}">📋 Todos</a>
                            <a href="/orders?status={status}&format=json" class="filter-btn">📄 JSON</a>
                        </div>
                    </div>
            """.format(
                pending_active="active" if status_filter == "pending" else "",
                shipped_active="active" if status_filter == "shipped" else "",
                delivered_active="active" if status_filter == "delivered" else "",
                error_active="active" if status_filter == "error" else "",
                all_active="active" if status_filter == "all" else "",
                status=status_filter
            )
            
            if not orders:
                html += """
                    <div class="empty-state">
                        <div style="font-size: 64px; margin-bottom: 20px;">📭</div>
                        <h2>Nenhum pedido encontrado</h2>
                        <p style="margin-top: 10px;">
                            Os pedidos aparecerão aqui quando forem faturados no Bagy
                        </p>
                    </div>
                """
            else:
                for order in orders:
                    status_class = f"status-{order['status']}"
                    status_text = {
                        "pending": "⏳ Aguardando",
                        "shipped": "📮 Enviado",
                        "delivered": "✅ Entregue",
                        "error": "❌ Erro"
                    }.get(order["status"], order["status"])
                    
                    parsed = order.get("parsed_data", {})
                    customer = parsed.get("customer", {}) if parsed else {}
                    address = parsed.get("address", {}) if parsed else {}
                    
                    html += f"""
                    <div class="order-card">
                        <div class="order-header">
                            <div>
                                <div class="order-id">Pedido #{order.get('bagy_order_code', order['bagy_order_id'])}</div>
                                <small style="color: #6c757d;">ID: {order['bagy_order_id']} | {order.get('created_at', 'N/A')}</small>
                            </div>
                            <span class="status {status_class}">{status_text}</span>
                        </div>
                        
                        <div class="order-info">
                            <div class="info-section">
                                <div class="info-title">👤 Cliente</div>
                                <div class="info-content">
                                    <div><strong>Nome:</strong> {order.get('customer_name', customer.get('name', 'N/A'))}</div>
                                    <div><strong>CPF:</strong> {order.get('customer_cpf', customer.get('cpf', 'N/A'))}</div>
                                    <div><strong>Email:</strong> {order.get('customer_email', customer.get('email', 'N/A'))}</div>
                                    <div><strong>Telefone:</strong> {order.get('customer_phone', customer.get('phone', 'N/A'))}</div>
                                </div>
                            </div>
                            
                            <div class="info-section">
                                <div class="info-title">📍 Endereço de Entrega</div>
                                <div class="info-content">
                                    <div><strong>CEP:</strong> {order.get('address_zipcode', address.get('zipcode', 'N/A'))}</div>
                                    <div><strong>Rua:</strong> {order.get('address_street', address.get('street', 'N/A'))}</div>
                                    <div><strong>Número:</strong> {order.get('address_number', address.get('number', 'N/A'))}</div>
                                    <div><strong>Complemento:</strong> {order.get('address_complement', address.get('complement', '-'))}</div>
                                    <div><strong>Bairro:</strong> {order.get('address_neighborhood', address.get('neighborhood', 'N/A'))}</div>
                                    <div><strong>Cidade:</strong> {order.get('address_city', address.get('city', 'N/A'))} - {order.get('address_state', address.get('state', 'N/A'))}</div>
                                </div>
                            </div>
                            
                            <div class="info-section">
                                <div class="info-title">💰 Valores</div>
                                <div class="info-content">
                                    <div><strong>Total:</strong> R$ {order.get('total_value', 0):.2f}</div>
                                    <div><strong>Frete:</strong> R$ {order.get('shipping_cost', 0):.2f}</div>
                                    {f'<div><strong>Rastreio:</strong> {order.get("tracking_code")}</div>' if order.get('tracking_code') else ''}
                                </div>
                                <button class="copy-btn" onclick="copyOrder('{order['bagy_order_id']}')">
                                    📋 Copiar Dados
                                </button>
                            </div>
                        </div>
                        
                        {f'<div style="margin-top: 15px; padding: 10px; background: #f8d7da; color: #721c24; border-radius: 5px;"><strong>Erro:</strong> {order.get("last_error")}</div>' if order.get('last_error') else ''}
                    </div>
                    """
            
            html += """
                </div>
                <script>
                    function copyOrder(orderId) {
                        // TODO: Implementar cópia para clipboard
                        alert('Funcionalidade de cópia em desenvolvimento. Por enquanto, copie manualmente os dados.');
                    }
                </script>
            </body>
            </html>
            """
            return html
        
        # Formato JSON
        return jsonify({
            "orders": orders,
            "count": len(orders),
            "status_filter": status_filter
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao listar pedidos: {e}")
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
