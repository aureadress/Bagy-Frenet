# 🚀 Integração Bagy → Frenet

Webhook Flask robusto e otimizado para **capturar pedidos faturados da Bagy**, salvar localmente com **painel web de visualização**, e permitir que você crie etiquetas manualmente na **Frenet** com monitoramento automático de entrega.

## 🎯 Como Funciona

1. **📥 Bagy dispara webhook** quando pedido é faturado (fulfillment_status = "invoiced")
2. **🚀 Sistema cria pedido automaticamente** na Frenet via API Shipments
3. **🏷️ Pedido aparece** em "Gerencie suas etiquetas" no painel Frenet
4. **👤 Você acessa** painel.frenet.com.br e escolhe a transportadora
5. **📄 Gera etiqueta** manualmente e imprime
6. **📦 Sistema monitora** rastreio automaticamente
7. **✅ Atualiza Bagy** quando pedido é entregue

## ✨ Funcionalidades

- ✅ **Recebe webhooks** da Bagy quando pedidos são faturados
- ✅ **Cria pedidos automaticamente** na Frenet via API Shipments
- ✅ **Pedidos aparecem** em "Gerencie suas etiquetas" no painel Frenet
- ✅ **Salva dados completos** no banco SQLite com campos estruturados
- ✅ **Painel web HTML** responsivo para visualizar pedidos (backup)
- ✅ **Filtros por status** (pending, shipped, delivered, error)
- ✅ **Export JSON** para integração com outras ferramentas
- ✅ **Monitor automático** verifica entregas periodicamente
- ✅ **Atualiza Bagy** automaticamente quando pedido é entregue
- ✅ **Retry inteligente** em caso de falhas
- ✅ **Logs detalhados** com emojis para fácil visualização
- ✅ **Health checks** e estatísticas em tempo real
- ✅ **100% pronto para produção**

## ✅ API da Frenet: Shipments

A API da Frenet oferece o endpoint **Shipments** para criação automática de pedidos:
- ✅ `POST /v1/shipments` - Cria pedido no painel "Gerencie suas etiquetas"
- ✅ `/shipping/quote` - Cotação de frete
- ✅ `/tracking/trackinginfo` - Rastreamento

**Como funciona:**
1. Sistema envia pedido via API Shipments
2. Pedido aparece automaticamente no painel Frenet
3. Você escolhe transportadora e gera etiqueta
4. Sistema monitora rastreio e atualiza Bagy automaticamente

**Documentação:** https://docs.frenet.com.br/docs/shipments-whitelabel

## 📋 Requisitos

- Python 3.11+
- Tokens de API:
  - `BAGY_TOKEN` - Token de autenticação da Bagy
  - `FRENET_TOKEN` - Token de autenticação da Frenet

## 🔧 Instalação Local

### 1. Clone o repositório

```bash
git clone <seu-repositorio>
cd <nome-do-projeto>
```

### 2. Crie ambiente virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instale dependências

```bash
pip install -r requirements.txt
```

### 4. Configure variáveis de ambiente

```bash
cp .env.example .env
# Edite .env e adicione seus tokens
```

### 5. Execute a aplicação

```bash
python main.py
```

A aplicação estará rodando em `http://localhost:3000`

## 🐳 Deploy com Docker

### Usando Docker Compose (Recomendado)

```bash
# Configure as variáveis no .env
cp .env.example .env
nano .env  # Edite com seus tokens

# Inicie o serviço
docker-compose up -d

# Verifique os logs
docker-compose logs -f

# Pare o serviço
docker-compose down
```

### Usando Docker diretamente

```bash
# Build da imagem
docker build -t bagy-frenet-webhook .

# Execute o container
docker run -d \
  -p 3000:3000 \
  -e BAGY_TOKEN="seu_token_aqui" \
  -e FRENET_TOKEN="seu_token_aqui" \
  -e SELLER_CEP="03320-001" \
  -e FORCE_VALUE="10.00" \
  -e FORCE_CARRIER_CODE="LOGGI" \
  -e FORCE_CARRIER_NAME="Entrega Loggi" \
  -v $(pwd)/data:/app/data \
  --name bagy-webhook \
  bagy-frenet-webhook
```

## ☁️ Deploy em Nuvem

### Railway.app

1. Faça fork deste repositório no GitHub
2. Acesse [Railway.app](https://railway.app) e crie uma conta
3. Clique em **"New Project" → "Deploy from GitHub"**
4. Selecione seu repositório
5. Adicione as variáveis de ambiente:
   - `BAGY_TOKEN`
   - `FRENET_TOKEN`
   - `SELLER_CEP` (opcional)
   - `FORCE_VALUE` (opcional)
   - `FORCE_CARRIER_CODE` (opcional)
   - `FORCE_CARRIER_NAME` (opcional)
6. Aguarde o deploy (Railway detectará automaticamente o Procfile)
7. Copie a URL gerada (ex: `https://seu-app.up.railway.app`)

### Render.com

1. Faça fork deste repositório no GitHub
2. Acesse [Render.com](https://render.com) e crie uma conta
3. Clique em **"New +" → "Web Service"**
4. Conecte seu repositório GitHub
5. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn main:app --bind 0.0.0.0:$PORT`
6. Adicione as variáveis de ambiente (mesmo que Railway)
7. Clique em **"Create Web Service"**

### Heroku

1. Instale o [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Faça login: `heroku login`
3. Crie o app:

```bash
heroku create seu-app-nome
```

4. Configure variáveis:

```bash
heroku config:set BAGY_TOKEN="seu_token"
heroku config:set FRENET_TOKEN="seu_token"
heroku config:set SELLER_CEP="03320-001"
```

5. Faça deploy:

```bash
git push heroku main
```

## 🔗 Configuração do Webhook na Bagy

Após fazer o deploy, configure o webhook na plataforma Bagy:

1. Acesse **Configurações → Integrações → Webhooks**
2. Clique em **"Adicionar Webhook"**
3. Configure:
   - **Evento:** `Pedido Faturado` ou `Order Invoiced`
   - **URL:** `https://bagy-frenet-production.up.railway.app/webhook`
   - **Método:** `POST`
   - **Content-Type:** `application/json`
4. Salve e teste enviando um pedido de teste

### URLs Suportadas

O sistema aceita webhooks em **3 endpoints** diferentes para máxima compatibilidade:
- `https://seu-app.railway.app/` (raiz)
- `https://seu-app.railway.app/webhook` (recomendado)
- `https://seu-app.railway.app/order`

Todos suportam **GET** e **POST** para compatibilidade com integrações nativas.

## 📋 Workflow Completo Passo a Passo

### 1️⃣ Cliente faz um pedido na Bagy
- Pedido entra com status "pending" ou "processing"

### 2️⃣ Você fatura o pedido na Bagy
- Muda status para "invoiced" (faturado)
- Bagy dispara webhook automaticamente

### 3️⃣ Sistema cria pedido automaticamente na Frenet
- Webhook captura dados completos do pedido
- Envia via API Shipments para Frenet
- Pedido é criado automaticamente
- Salva no banco de dados local (backup)
- Status inicial: `pending`

### 4️⃣ Pedido aparece no painel Frenet
- Acesse [painel.frenet.com.br](https://painel.frenet.com.br)
- Vá em "Gerencie suas etiquetas"
- Pedido está lá automaticamente! 🎉

### 5️⃣ Você escolhe transportadora e gera etiqueta
- Escolha transportadora (recomendado: Loggi Drop Off)
- Gere a etiqueta
- Imprima e cole no pacote

### 6️⃣ Faça a postagem
- Leve o pacote ao ponto de coleta
- Ou aguarde coleta no local

### 7️⃣ Sistema monitora automaticamente
- A cada 10 minutos, verifica status no rastreio
- Quando detecta "entregue", atualiza a Bagy
- Pedido fica com status `delivered` no banco

### 8️⃣ Cliente recebe e tudo está sincronizado!
- Bagy mostra pedido como entregue
- Frenet tem registro da entrega
- Sistema local tem registro completo
- Processo finalizado ✅

## 📊 Endpoints da API

### `GET /`
Health check básico

**Resposta:**
```json
{
  "status": "online",
  "service": "Webhook Bagy-Frenet",
  "message": "🚀 Serviço ativo e monitorando pedidos",
  "version": "2.0"
}
```

### `GET /health`
Health check detalhado com estatísticas

**Resposta:**
```json
{
  "status": "healthy",
  "timestamp": "2024-10-30T10:30:00",
  "configuration": {
    "bagy_token_configured": true,
    "frenet_token_configured": true,
    "seller_cep": "03320-001",
    "force_value": 10.0,
    "carrier": "Entrega Loggi",
    "tracker_interval": 600
  },
  "database": {
    "path": "data.db",
    "stats": {
      "created": 5,
      "shipped": 12,
      "delivered": 8,
      "error": 1,
      "total": 26
    }
  }
}
```

### `GET /stats`
Estatísticas de pedidos

**Resposta:**
```json
{
  "statistics": {
    "created": 5,
    "shipped": 12,
    "delivered": 8,
    "error": 1,
    "total": 26
  },
  "timestamp": "2024-10-30T10:30:00"
}
```

### `GET /orders`
🆕 **Painel web para visualizar pedidos salvos**

**Parâmetros de query:**
- `status` - Filtrar por status: `pending`, `shipped`, `delivered`, `error`, `all` (padrão: `pending`)
- `format` - Formato de resposta: `html` (padrão), `json`

**Exemplos:**
- `https://seu-app.railway.app/orders` - Painel HTML com pedidos pendentes
- `https://seu-app.railway.app/orders?status=all` - Todos os pedidos
- `https://seu-app.railway.app/orders?status=pending&format=json` - JSON de pendentes

**Resposta HTML:**
Interface web bonita com:
- Cards de pedidos com dados completos
- Filtros por status (pendente, enviado, entregue, erro)
- Informações de cliente, endereço e valores
- Botão para copiar dados
- Design responsivo

**Resposta JSON:**
```json
{
  "orders": [
    {
      "id": 1,
      "bagy_order_id": "12345",
      "bagy_order_code": "TEST-2025-001",
      "status": "pending",
      "customer_name": "Maria Silva",
      "customer_cpf": "12345678901",
      "customer_email": "maria@exemplo.com",
      "customer_phone": "11987654321",
      "address_zipcode": "01310100",
      "address_street": "Avenida Paulista",
      "address_number": "1578",
      "address_complement": "Andar 5",
      "address_neighborhood": "Bela Vista",
      "address_city": "São Paulo",
      "address_state": "SP",
      "total_value": 199.90,
      "shipping_cost": 10.00,
      "tracking_code": null,
      "created_at": "2025-10-30 19:58:40",
      "updated_at": "2025-10-30 19:58:40"
    }
  ],
  "count": 1,
  "status_filter": "pending"
}
```

### `POST /webhook`
Recebe webhooks da Bagy (configurado automaticamente)

**Requisição (enviada pela Bagy):**
```json
{
  "id": "123456",
  "fulfillment_status": "invoiced",
  "customer": {
    "name": "João Silva",
    "email": "joao@email.com",
    "phone": "11999999999"
  },
  "address": {
    "zipcode": "01310-100",
    "street": "Av. Paulista, 1000",
    "city": "São Paulo",
    "state": "SP"
  },
  "items": [
    {
      "weight": 1.5,
      "length": 20,
      "height": 10,
      "width": 15,
      "quantity": 2
    }
  ]
}
```

**Resposta (sucesso):**
```json
{
  "success": true,
  "order_id": "123456",
  "tracking_code": "FR123456789BR",
  "message": "Pedido enviado à Frenet e marcado como enviado na Bagy"
}
```

## ⚙️ Variáveis de Ambiente

| Variável | Obrigatória | Padrão | Descrição |
|----------|-------------|--------|-----------|
| `BAGY_TOKEN` | ✅ Sim | - | Token de autenticação da API Bagy |
| `FRENET_TOKEN` | ✅ Sim | - | Token de autenticação da API Frenet |
| `BAGY_BASE` | ❌ Não | `https://api.dooca.store` | URL base da API Bagy |
| `FRENET_SHIPMENTS_URL` | ❌ Não | `https://api.frenet.com.br/v1/shipments` | URL da API de criação de pedidos Frenet |
| `FRENET_QUOTE_URL` | ❌ Não | `https://api.frenet.com.br/shipping/quote` | URL da API de cotação Frenet |
| `FRENET_TRACK_URL` | ❌ Não | `https://api.frenet.com.br/tracking/trackinginfo` | URL da API de rastreio Frenet |
| `SELLER_CEP` | ❌ Não | `03320-001` | CEP do remetente |
| `FORCE_VALUE` | ❌ Não | `10.00` | Valor fixo do frete (R$) |
| `FORCE_CARRIER_CODE` | ❌ Não | `LOG_DRPOFF` | Código da transportadora (ex: LOG_DRPOFF para Loggi Drop Off) |
| `FORCE_CARRIER_NAME` | ❌ Não | `Loggi Drop Off` | Nome da transportadora |
| `TRACKER_INTERVAL` | ❌ Não | `600` | Intervalo de verificação de rastreio (segundos) |
| `DB_PATH` | ❌ Não | `data.db` | Caminho do banco de dados SQLite |
| `MAX_RETRIES` | ❌ Não | `3` | Número máximo de tentativas em caso de erro |
| `REQUEST_TIMEOUT` | ❌ Não | `30` | Timeout de requisições HTTP (segundos) |
| `PORT` | ❌ Não | `3000` | Porta do servidor |

### 🔌 Configuração Avançada de Endpoints

A integração é **flexível** e permite usar qualquer API de envio!

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `INTEGRATION_TYPE` | `frenet` | Tipo: `frenet`, `loggi`, `kangu`, `custom` |
| `SHIPPING_API_URL` | `https://api.frenet.com.br/shipping/quote` | URL da API de envio |
| `TRACKING_API_URL` | `https://api.frenet.com.br/tracking/trackinginfo` | URL da API de rastreio |

#### Exemplos de configuração:

**Usar Frenet (padrão):**
```env
INTEGRATION_TYPE=frenet
SHIPPING_API_URL=https://api.frenet.com.br/shipping/quote
```

**Usar Loggi diretamente:**
```env
INTEGRATION_TYPE=loggi
SHIPPING_API_URL=https://api.loggi.com/v1/shipments
FRENET_TOKEN=seu_token_loggi_aqui
```

**Usar Kangu:**
```env
INTEGRATION_TYPE=kangu
SHIPPING_API_URL=https://portal.kangu.com.br/tms/transporte/solicitar
FRENET_TOKEN=seu_token_kangu_aqui
```

**API customizada:**
```env
INTEGRATION_TYPE=custom
SHIPPING_API_URL=https://sua-api.com/v1/criar-envio
TRACKING_API_URL=https://sua-api.com/v1/rastreio
```

#### Headers por tipo de integração:

- **Frenet:** `Authorization: Basic {token}`
- **Loggi:** `Authorization: Bearer {token}`
- **Kangu:** `token: {token}`
- **Custom:** `Authorization: Basic {token}` (padrão)

## 🔍 Logs e Monitoramento

A aplicação gera logs detalhados com emojis para facilitar identificação:

```
2024-10-30 10:30:15 - __main__ - INFO - 🚀 INICIANDO WEBHOOK BAGY-FRENET
2024-10-30 10:30:15 - __main__ - INFO - 🔧 Configurações carregadas: SELLER_CEP=03320-001, FORCE_VALUE=R$10.0, CARRIER=Entrega Loggi
2024-10-30 10:30:15 - __main__ - INFO - ✅ Banco de dados inicializado: data.db
2024-10-30 10:30:15 - __main__ - INFO - ✅ Worker de rastreio iniciado
2024-10-30 10:30:15 - __main__ - INFO - 🌐 Servidor Flask iniciando na porta 3000...
2024-10-30 10:31:22 - __main__ - INFO - 📥 Webhook recebido para pedido 123456
2024-10-30 10:31:23 - __main__ - INFO - 🚚 Enviando pedido 123456 para Frenet...
2024-10-30 10:31:24 - __main__ - INFO - ✅ Pedido 123456 enviado à Frenet com rastreio: FR123456789BR
2024-10-30 10:31:25 - __main__ - INFO - 📤 Marcando pedido 123456 como enviado na Bagy...
2024-10-30 10:31:26 - __main__ - INFO - ✅ Pedido 123456 marcado como enviado na Bagy
2024-10-30 10:31:26 - __main__ - INFO - ✅ Pedido 123456 processado com sucesso! Rastreio: FR123456789BR
```

### Tipos de log:
- 🚀 Inicialização
- 📥 Webhook recebido
- 🚚 Enviando para Frenet
- 📤 Atualizando Bagy
- 📦 Entrega confirmada
- ✅ Sucesso
- ⚠️ Avisos
- ❌ Erros
- 🔍 Verificações
- 💤 Aguardando

## 🗄️ Banco de Dados

A aplicação usa SQLite para persistência. Estrutura da tabela `orders`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | INTEGER | ID interno (autoincrement) |
| `bagy_order_id` | TEXT | ID do pedido na Bagy (único) |
| `tracking_code` | TEXT | Código de rastreio da Frenet |
| `status` | TEXT | Status: created, shipped, delivered, error |
| `created_at` | TEXT | Data de criação |
| `updated_at` | TEXT | Última atualização |
| `delivered_at` | TEXT | Data de entrega |
| `retry_count` | INTEGER | Contagem de tentativas |
| `last_error` | TEXT | Última mensagem de erro |

## 🧪 Testes

### Teste local

```bash
# Inicie a aplicação
python main.py

# Em outro terminal, teste o webhook
curl -X POST http://localhost:3000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "id": "TEST-123",
    "fulfillment_status": "invoiced",
    "customer": {"name": "Teste", "email": "teste@email.com", "phone": "11999999999"},
    "address": {"zipcode": "01310-100", "street": "Av. Paulista, 1000", "city": "São Paulo", "state": "SP"},
    "items": [{"weight": 1, "length": 20, "height": 10, "width": 15, "quantity": 1}]
  }'

# Verifique o health check
curl http://localhost:3000/health

# Veja as estatísticas
curl http://localhost:3000/stats
```

## 🔒 Segurança

- ✅ Tokens nunca expostos nos logs
- ✅ Validação de dados de entrada
- ✅ Timeout em requisições HTTP
- ✅ Retry com backoff
- ✅ Tratamento robusto de erros
- ✅ Logs detalhados sem informações sensíveis

## 🐛 Troubleshooting

### Erro: "BAGY_TOKEN não configurado"
**Solução:** Configure a variável de ambiente `BAGY_TOKEN` com seu token da Bagy.

### Erro: "FRENET_TOKEN não configurado"
**Solução:** Configure a variável de ambiente `FRENET_TOKEN` com seu token da Frenet.

### Webhook não está sendo recebido
**Soluções:**
1. Verifique se a URL está correta na configuração da Bagy
2. Verifique se a aplicação está rodando e acessível publicamente
3. Teste manualmente com `curl` para validar

### Pedidos não são marcados como entregues
**Soluções:**
1. Verifique os logs para ver se há erros na consulta à Frenet
2. Verifique se `TRACKER_INTERVAL` não está muito alto
3. Confirme que o código de rastreio está correto no banco

### Erro ao conectar com APIs
**Soluções:**
1. Verifique sua conexão com internet
2. Confirme que os tokens estão válidos
3. Verifique se as URLs das APIs estão corretas
4. Aumente `REQUEST_TIMEOUT` se necessário

## 📈 Performance

- **Retry automático:** Até 3 tentativas em caso de falha
- **Worker assíncrono:** Monitoramento em thread separada
- **Banco indexado:** Queries otimizadas com índices
- **Timeout configurável:** Evita travamentos
- **Logs eficientes:** Debug opcional para reduzir verbosidade

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit suas mudanças: `git commit -m 'Adiciona nova funcionalidade'`
4. Push para a branch: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

## 📝 Licença

Este projeto é de código aberto e está disponível sob a licença MIT.

## 💡 Suporte

Se encontrar problemas ou tiver dúvidas:
1. Verifique a seção de **Troubleshooting**
2. Consulte os logs da aplicação
3. Abra uma issue no GitHub

---

**Desenvolvido com ❤️ para automatizar integrações Bagy-Frenet**
