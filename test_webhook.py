#!/usr/bin/env python3
"""
Script de teste para o webhook Bagy-Frenet
"""

import requests
import json
import sys

def test_webhook(url="http://localhost:3000"):
    """Testa os endpoints do webhook."""
    
    print("="*60)
    print("🧪 TESTANDO WEBHOOK BAGY-FRENET")
    print("="*60)
    
    # Teste 1: Health Check Básico
    print("\n1️⃣  Testando health check básico (GET /)...")
    try:
        response = requests.get(f"{url}/", timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Resposta: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        assert response.status_code == 200, "Status deveria ser 200"
        print("   ✅ Teste passou!")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 2: Health Check Detalhado
    print("\n2️⃣  Testando health check detalhado (GET /health)...")
    try:
        response = requests.get(f"{url}/health", timeout=10)
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Status do serviço: {data.get('status')}")
        print(f"   Configurações OK: {data.get('configuration', {})}")
        print("   ✅ Teste passou!")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 3: Estatísticas
    print("\n3️⃣  Testando endpoint de estatísticas (GET /stats)...")
    try:
        response = requests.get(f"{url}/stats", timeout=10)
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Estatísticas: {json.dumps(data.get('statistics', {}), indent=2)}")
        print("   ✅ Teste passou!")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 4: Webhook com pedido não faturado (deve ignorar)
    print("\n4️⃣  Testando webhook com pedido NÃO faturado (deve ignorar)...")
    try:
        payload = {
            "id": "TEST-001",
            "fulfillment_status": "pending",
            "customer": {
                "name": "Cliente Teste",
                "email": "teste@email.com",
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
                    "quantity": 1
                }
            ]
        }
        response = requests.post(f"{url}/webhook", json=payload, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Resposta: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        assert response.status_code == 200, "Deve retornar 200 para pedido não faturado"
        print("   ✅ Teste passou! (Pedido ignorado corretamente)")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 5: Webhook com pedido faturado (vai tentar processar)
    print("\n5️⃣  Testando webhook com pedido FATURADO (tentará processar)...")
    print("   ⚠️  Nota: Este teste pode falhar se os tokens não estiverem configurados")
    try:
        payload = {
            "id": "TEST-002",
            "fulfillment_status": "invoiced",
            "customer": {
                "name": "Cliente Teste",
                "email": "teste@email.com",
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
                    "quantity": 1
                }
            ]
        }
        response = requests.post(f"{url}/webhook", json=payload, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Resposta: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200:
            print("   ✅ Teste passou! (Pedido processado com sucesso)")
        elif response.status_code == 500:
            print("   ⚠️  Pedido não processado (esperado se tokens não configurados)")
        else:
            print(f"   ⚠️  Status inesperado: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Erro (esperado se tokens não configurados): {e}")
    
    # Teste 6: Webhook sem ID
    print("\n6️⃣  Testando webhook SEM ID (deve rejeitar)...")
    try:
        payload = {
            "fulfillment_status": "invoiced",
            "customer": {"name": "Teste"},
            "address": {"zipcode": "01310-100"}
        }
        response = requests.post(f"{url}/webhook", json=payload, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Resposta: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        assert response.status_code == 400, "Deve retornar 400 para pedido sem ID"
        print("   ✅ Teste passou! (Pedido rejeitado corretamente)")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    print("\n" + "="*60)
    print("✅ TODOS OS TESTES CONCLUÍDOS!")
    print("="*60)
    return True

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
    print(f"Testando URL: {url}\n")
    
    try:
        success = test_webhook(url)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erro fatal: {e}")
        sys.exit(1)
