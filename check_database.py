#!/usr/bin/env python3
"""
Script para verificar o banco de dados e logs de pedidos
"""
import sqlite3
import json
from datetime import datetime

DB_PATH = "data.db"

def check_database():
    """Verifica pedidos no banco de dados"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Listar todos os pedidos
        cursor.execute("""
            SELECT id, bagy_order_id, status, tracking_code, created_at, last_error
            FROM orders
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        pedidos = cursor.fetchall()
        
        print("=" * 80)
        print(f"📊 PEDIDOS NO BANCO DE DADOS ({len(pedidos)} encontrados)")
        print("=" * 80)
        
        for pedido in pedidos:
            id_interno, bagy_id, status, tracking, created, error_log = pedido
            print(f"\n🔹 Pedido #{id_interno}")
            print(f"   Bagy Order ID: {bagy_id}")
            print(f"   Status: {status}")
            print(f"   Tracking: {tracking or 'N/A'}")
            print(f"   Criado em: {created}")
            
            if error_log:
                print(f"   ⚠️ ERRO: {error_log}")
        
        # Estatísticas
        cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
        stats = cursor.fetchall()
        
        print("\n" + "=" * 80)
        print("📈 ESTATÍSTICAS")
        print("=" * 80)
        for status, count in stats:
            print(f"   {status}: {count} pedido(s)")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro ao verificar banco: {e}")

if __name__ == "__main__":
    check_database()
