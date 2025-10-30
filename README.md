# 🚀 Integração Bagy → Frenet

Webhook Flask robusto e otimizado para automatizar o envio de pedidos faturados da **Bagy** para a **Frenet** com monitoramento automático de entrega.

## ✨ Funcionalidades

- ✅ **Recebe webhooks** da Bagy quando pedidos são faturados
- ✅ **Envia automaticamente** para Frenet com valor e transportadora configuráveis
- ✅ **Atualiza status** na Bagy (enviado → entregue)
- ✅ **Monitor automático** verifica entregas periodicamente
- ✅ **Retry inteligente** em caso de falhas
- ✅ **Logs detalhados** com emojis para fácil visualização
- ✅ **Health checks** e estatísticas em tempo real
- ✅ **Banco SQLite** para persistência e controle
- ✅ **100% pronto para produção**

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
   - **URL:** `https://sua-url.com/webhook`
   - **Método:** `POST`
   - **Content-Type:** `application/json`
4. Salve e teste enviando um pedido de teste

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
| `FRENET_QUOTE_URL` | ❌ Não | `https://api.frenet.com.br/shipping/quote` | URL da API de cotação Frenet |
| `FRENET_TRACK_URL` | ❌ Não | `https://api.frenet.com.br/tracking/trackinginfo` | URL da API de rastreio Frenet |
| `SELLER_CEP` | ❌ Não | `03320-001` | CEP do remetente |
| `FORCE_VALUE` | ❌ Não | `10.00` | Valor fixo do frete (R$) |
| `FORCE_CARRIER_CODE` | ❌ Não | `LOGGI` | Código da transportadora |
| `FORCE_CARRIER_NAME` | ❌ Não | `Entrega Loggi` | Nome da transportadora |
| `TRACKER_INTERVAL` | ❌ Não | `600` | Intervalo de verificação de rastreio (segundos) |
| `DB_PATH` | ❌ Não | `data.db` | Caminho do banco de dados SQLite |
| `MAX_RETRIES` | ❌ Não | `3` | Número máximo de tentativas em caso de erro |
| `REQUEST_TIMEOUT` | ❌ Não | `30` | Timeout de requisições HTTP (segundos) |
| `PORT` | ❌ Não | `3000` | Porta do servidor |

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
