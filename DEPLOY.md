# 🚀 Guia de Deploy - Webhook Bagy-Frenet

## 📦 Repositório GitHub
**URL:** https://github.com/aureadress/Bagy-Frenet

---

## ⚡ Deploy Rápido (Railway.app - Recomendado)

### Por que Railway?
- ✅ Deploy automático via GitHub
- ✅ HTTPS gratuito
- ✅ Logs em tempo real
- ✅ Fácil gerenciamento de variáveis
- ✅ Free tier generoso

### Passo a Passo

#### 1. Acesse Railway
🔗 https://railway.app

#### 2. Conecte GitHub
- Clique em **"New Project"**
- Selecione **"Deploy from GitHub repo"**
- Autorize Railway a acessar seu GitHub
- Selecione o repositório: **aureadress/Bagy-Frenet**

#### 3. Configure Variáveis de Ambiente
Clique na aba **"Variables"** e adicione:

```env
BAGY_TOKEN=seu_token_bagy_aqui
FRENET_TOKEN=seu_token_frenet_aqui
```

**Opcionais (já têm valores padrão):**
```env
SELLER_CEP=03320-001
FORCE_VALUE=10.00
FORCE_CARRIER_CODE=LOGGI
FORCE_CARRIER_NAME=Entrega Loggi
TRACKER_INTERVAL=600
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```

#### 4. Deploy Automático
Railway detectará automaticamente o `Procfile` e iniciará o deploy!

#### 5. Obtenha a URL
- Na aba **"Settings"**
- Clique em **"Generate Domain"**
- Copie a URL gerada (ex: `https://bagy-frenet-production.up.railway.app`)

#### 6. Teste o Deploy
```bash
curl https://sua-url.up.railway.app/health
```

---

## 🌐 Deploy Alternativo (Render.com)

### Passo a Passo

#### 1. Acesse Render
🔗 https://render.com

#### 2. Novo Web Service
- Clique em **"New +"** → **"Web Service"**
- Conecte seu repositório GitHub: **aureadress/Bagy-Frenet**

#### 3. Configure o Serviço
- **Name:** `bagy-frenet-webhook`
- **Environment:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn main:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

#### 4. Adicione Variáveis de Ambiente
Na seção **"Environment"**, adicione:
```env
BAGY_TOKEN=seu_token_bagy_aqui
FRENET_TOKEN=seu_token_frenet_aqui
```

#### 5. Deploy
Clique em **"Create Web Service"** e aguarde o deploy!

---

## 💜 Deploy Alternativo (Heroku)

### Passo a Passo

#### 1. Instale Heroku CLI
```bash
# MacOS
brew install heroku/brew/heroku

# Windows
# Baixe de: https://devcenter.heroku.com/articles/heroku-cli

# Linux
curl https://cli-assets.heroku.com/install.sh | sh
```

#### 2. Login no Heroku
```bash
heroku login
```

#### 3. Clone o Repositório (se ainda não tiver)
```bash
git clone https://github.com/aureadress/Bagy-Frenet.git
cd Bagy-Frenet
```

#### 4. Crie o App no Heroku
```bash
heroku create seu-app-nome
```

#### 5. Configure Variáveis de Ambiente
```bash
heroku config:set BAGY_TOKEN="seu_token_bagy_aqui"
heroku config:set FRENET_TOKEN="seu_token_frenet_aqui"
heroku config:set SELLER_CEP="03320-001"
heroku config:set FORCE_VALUE="10.00"
heroku config:set FORCE_CARRIER_CODE="LOGGI"
heroku config:set FORCE_CARRIER_NAME="Entrega Loggi"
```

#### 6. Deploy
```bash
git push heroku main
```

#### 7. Verifique o Deploy
```bash
heroku logs --tail
heroku open
```

---

## 🐳 Deploy com Docker (Servidor Próprio)

### Usando Docker Compose (Recomendado)

#### 1. Clone o Repositório
```bash
git clone https://github.com/aureadress/Bagy-Frenet.git
cd Bagy-Frenet
```

#### 2. Configure Variáveis
```bash
cp .env.example .env
nano .env  # Edite com seus tokens
```

#### 3. Inicie os Containers
```bash
docker-compose up -d
```

#### 4. Verifique os Logs
```bash
docker-compose logs -f
```

#### 5. Pare os Containers
```bash
docker-compose down
```

### Usando Docker Diretamente

```bash
# Build
docker build -t bagy-frenet-webhook .

# Run
docker run -d \
  -p 3000:3000 \
  -e BAGY_TOKEN="seu_token" \
  -e FRENET_TOKEN="seu_token" \
  -v $(pwd)/data:/app/data \
  --name bagy-webhook \
  bagy-frenet-webhook

# Logs
docker logs -f bagy-webhook

# Stop
docker stop bagy-webhook
docker rm bagy-webhook
```

---

## 🔧 Configurar Webhook na Bagy

Após fazer o deploy, configure o webhook na plataforma Bagy:

### Passo a Passo

1. **Acesse a Bagy**
   - Faça login na sua conta Bagy
   - Vá para **Configurações**

2. **Navegue até Webhooks**
   - **Configurações** → **Integrações** → **Webhooks**

3. **Adicione Novo Webhook**
   - Clique em **"Adicionar Webhook"** ou **"Novo Webhook"**

4. **Configure o Webhook**
   ```
   Evento: Pedido Faturado (Order Invoiced)
   URL: https://sua-url.com/webhook
   Método: POST
   Content-Type: application/json
   ```

5. **Salve e Teste**
   - Salve as configurações
   - Faça um pedido teste e marque como faturado
   - Verifique os logs do seu webhook

---

## ✅ Verificar Deploy

### 1. Health Check
```bash
curl https://sua-url.com/health
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "configuration": {
    "bagy_token_configured": true,
    "frenet_token_configured": true,
    ...
  }
}
```

### 2. Estatísticas
```bash
curl https://sua-url.com/stats
```

### 3. Teste Manual do Webhook
```bash
curl -X POST https://sua-url.com/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "id": "TEST-123",
    "fulfillment_status": "invoiced",
    "customer": {
      "name": "Teste",
      "email": "teste@email.com",
      "phone": "11999999999"
    },
    "address": {
      "zipcode": "01310-100",
      "street": "Av. Paulista, 1000",
      "city": "São Paulo",
      "state": "SP"
    },
    "items": [{
      "weight": 1.5,
      "length": 20,
      "height": 10,
      "width": 15,
      "quantity": 1
    }]
  }'
```

---

## 📊 Monitoramento

### Logs em Tempo Real

**Railway:**
```bash
# Via dashboard
railway logs
```

**Render:**
```bash
# Via dashboard, seção "Logs"
```

**Heroku:**
```bash
heroku logs --tail --app seu-app-nome
```

**Docker:**
```bash
docker-compose logs -f
# ou
docker logs -f bagy-webhook
```

### Métricas Importantes

- **Taxa de sucesso** dos webhooks
- **Tempo de resposta** das APIs
- **Erros** e retry automático
- **Status de entrega** dos pedidos

---

## 🔒 Segurança

### ✅ Boas Práticas Implementadas

- Tokens armazenados em variáveis de ambiente
- Validação de entrada em todos os endpoints
- Timeout em requisições HTTP
- Retry automático com limite
- Logs sem informações sensíveis
- HTTPS obrigatório (via plataforma de deploy)

### 🚨 Atenção

- **NUNCA** commite tokens no Git
- Use `.env` para desenvolvimento local
- Variáveis de ambiente para produção
- Mantenha tokens seguros e privados

---

## 🆘 Troubleshooting

### Erro: "BAGY_TOKEN não configurado"
**Solução:** Configure a variável `BAGY_TOKEN` no painel da plataforma de deploy

### Erro: "FRENET_TOKEN não configurado"
**Solução:** Configure a variável `FRENET_TOKEN` no painel da plataforma de deploy

### Webhook não está sendo recebido
**Soluções:**
1. Verifique se a URL está correta na Bagy
2. Teste manualmente com `curl` (veja exemplo acima)
3. Verifique os logs do servidor
4. Confirme que a aplicação está rodando (`/health`)

### Deploy falhou
**Soluções:**
1. Verifique os logs de build
2. Confirme que todas as dependências estão em `requirements.txt`
3. Verifique se o `Procfile` está correto
4. Tente fazer redeploy manual

### Pedidos não são atualizados na Bagy
**Soluções:**
1. Verifique se `BAGY_TOKEN` está correto
2. Confirme permissões do token na Bagy
3. Veja os logs para mensagens de erro
4. Teste o endpoint de health check

---

## 📞 Suporte

- 📧 Issues no GitHub: https://github.com/aureadress/Bagy-Frenet/issues
- 📚 Documentação: README.md
- 🔍 Logs detalhados disponíveis na aplicação

---

## 🎉 Pronto!

Seu webhook Bagy-Frenet está agora em produção! 🚀

**Próximos passos:**
1. Configure o webhook na Bagy
2. Faça um pedido teste
3. Monitore os logs
4. Acompanhe as entregas automaticamente

**Tudo funcionando? Aproveite a automação! ✨**
