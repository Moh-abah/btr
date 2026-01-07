# app/services/indicator_state_service.py
import json
from datetime import datetime
import sqlite3

class IndicatorStateService:
    async def save_active_monitoring(self, symbol: str, indicators: list):
        """حفظ الرموز تحت المراقبة ومؤشراتها"""
        state_data = {
            "symbol": symbol,
            "indicators": indicators,
            "last_updated": datetime.utcnow().isoformat(),
            "is_active": True
        }

        # حفظ دائم في SQLite فقط
        await self.save_to_permanent_storage(symbol, state_data)

    async def load_all_active_monitoring(self):
        """تحميل جميع الرموز تحت المراقبة"""
        conn = sqlite3.connect('indicators_state.db')
        cursor = conn.cursor()

        # التأكد من وجود الجدول
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator_states (
                symbol TEXT PRIMARY KEY,
                indicators_json TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')

        # جلب جميع الرموز
        cursor.execute("SELECT symbol, indicators_json FROM indicator_states")
        rows = cursor.fetchall()
        conn.close()

        active_symbols = []
        for symbol, indicators_json in rows:
            active_symbols.append({
                "symbol": symbol,
                "indicators": json.loads(indicators_json),
                "is_active": True
            })
        return active_symbols

    async def resume_monitoring_on_startup(self):
        """استئناف المراقبة عند إعادة تشغيل السيرفر"""
        active_symbols = await self.load_all_active_monitoring()

        from app.providers.binance_indicators_stream import indicators_manager

        for symbol_data in active_symbols:
            print(f"Resuming monitoring for {symbol_data['symbol']}")
            # إعادة تشغيل المراقبة
            await indicators_manager.add_symbol_monitoring(
                symbol_data['symbol'],
                symbol_data['indicators']
            )

    async def save_to_permanent_storage(self, symbol: str, data: dict):
        """حفظ دائم في SQLite"""
        conn = sqlite3.connect('indicators_state.db')
        cursor = conn.cursor()

        # إنشاء الجدول إذا لم يكن موجوداً
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicator_states (
                symbol TEXT PRIMARY KEY,
                indicators_json TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')

        # إدخال أو تحديث البيانات
        cursor.execute('''
            INSERT OR REPLACE INTO indicator_states 
            (symbol, indicators_json, updated_at)
            VALUES (?, ?, ?)
        ''', (symbol, json.dumps(data['indicators']), datetime.utcnow()))

        conn.commit()
        conn.close()

# إنشاء النسخة الوحيدة
state_service = IndicatorStateService()
