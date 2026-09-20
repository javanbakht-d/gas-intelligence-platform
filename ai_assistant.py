"""
Phase 10: AI Analytical Assistant - نسخه 2.0
با تشخیص ورودی عددی و الگوهای بهبودیافته
"""

import sqlite3
import re
from datetime import datetime
from typing import Dict, List, Any

DB_FILE = "gas_data.db"


class GasAIAssistant:
    """دستیار هوشمند تحلیلی گاز"""
    
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.conversation_context = {}
        
        self.sample_questions = [
            "کدام استان بیشترین مصرف را دارد؟",
            "پیش‌بینی ۷ روز آینده",
            "اگر دما ۵ درجه سردتر شود چه اتفاقی می‌افتد؟",
            "بهترین مدل پیش‌بینی چیست؟",
            "مصرف استان تهران چقدر است؟",
        ]
        
        self.intent_patterns = {
            'top_consumption_provinces': [
                r'کدام استان', r'بیشترین.*استان', r'پرمصرف.*استان',
                r'استان.*بیشترین', r'رتبه.*استان',
            ],
            'province_consumption': [
                r'مصرف.*استان', r'استان.*مصرف',
            ],
            'forecast': [
                r'پیش.?بینی', r'آینده', r'فردا', r'هفته آینده',
            ],
            'temperature_scenario': [
                r'اگر.*دما', r'اگر.*سرد', r'اگر.*گرم', r'سناریو',
            ],
            'anomalies': [r'ناهنجاری', r'غیرعادی', r'عجیب'],
            'top_stations': [
                r'ایستگاه.*بیشترین', r'پرمصرف.*ایستگاه',
            ],
            'model_performance': [
                r'بهترین مدل', r'دقت مدل', r'عملکرد مدل',
            ],
            'temperature_correlation': [
                r'رابطه.*دما', r'همبستگی.*دما', r'اثر.*دما',
            ],
            'total_consumption': [r'کل مصرف', r'مصرف کل', r'مجموع مصرف'],
        }
    
    def _clean_text(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        fa_digits = '۰۱۲۳۴۵۶۷۸۹'
        en_digits = '0123456789'
        for fa, en in zip(fa_digits, en_digits):
            text = text.replace(fa, en)
        return text
    
    def _detect_intent(self, question: str) -> str:
        question_lower = question.lower()
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, question_lower):
                    return intent
        return 'unknown'
    
    def _extract_entities(self, question: str) -> Dict[str, Any]:
        entities = {}
        
        provinces = ['تهران', 'اصفهان', 'فارس', 'خراسان', 'آذربایجان',
                     'مازندران', 'گیلان', 'کرمان', 'خوزستان', 'بوشهر',
                     'قم', 'سمنان', 'اردبیل']
        for prov in provinces:
            if prov in question:
                entities['province'] = prov
                break
        
        numbers = re.findall(r'\d+', question)
        if numbers:
            entities['number'] = int(numbers[0])
        
        if 'برتر' in question or 'اول' in question:
            match = re.search(r'(\d+)', question)
            if match:
                entities['top_n'] = int(match.group(1))
            else:
                entities['top_n'] = 5
        
        return entities
    
    def _execute_safe_query(self, query: str, params: tuple = ()) -> List[Dict]:
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"⚠️ خطا: {e}")
            return []
    
    def _handle_top_provinces(self, entities: Dict) -> Dict:
        limit = min(entities.get('top_n', 5), 20)
        query = """
            SELECT استان, SUM(میزان_مصرف) as total_consumption,
                   COUNT(DISTINCT نام_ایستگاه) as station_count
            FROM station_consumption_daily WHERE استان IS NOT NULL
            GROUP BY استان ORDER BY total_consumption DESC LIMIT ?
        """
        results = self._execute_safe_query(query, (limit,))
        
        if not results:
            return {'text': 'داده‌ای یافت نشد.', 'type': 'error'}
        
        text = f"🏆 **{limit} استان پرمصرف کشور:**\n\n"
        for i, r in enumerate(results, 1):
            text += f"{i}. **{r['استان']}**: {r['total_consumption']:,.0f} واحد ({r['station_count']} ایستگاه)\n"
        
        top = results[0]['استان']
        text += f"\n💡 **نتیجه:** استان {top} بیشترین مصرف گاز را دارد."
        
        return {'text': text, 'type': 'table', 'data': results, 'visualization': 'bar'}
    
    def _handle_province_consumption(self, entities: Dict) -> Dict:
        province = entities.get('province')
        if not province:
            return {'text': 'لطفاً نام استان را مشخص کنید.', 'type': 'clarification'}
        
        query = """
            SELECT استان, SUM(میزان_مصرف) as total_consumption,
                   AVG(میزان_مصرف) as avg_consumption, COUNT(*) as record_count,
                   COUNT(DISTINCT نام_ایستگاه) as station_count
            FROM station_consumption_daily WHERE استان LIKE ? GROUP BY استان
        """
        results = self._execute_safe_query(query, (f'%{province}%',))
        
        if not results:
            return {'text': f'اطلاعاتی برای استان {province} یافت نشد.', 'type': 'error'}
        
        r = results[0]
        text = f"📊 **تحلیل مصرف استان {r['استان']}:**\n\n"
        text += f"- مجموع مصرف: **{r['total_consumption']:,.0f}** واحد\n"
        text += f"- میانگین مصرف: **{r['avg_consumption']:,.0f}** واحد\n"
        text += f"- تعداد ایستگاه‌ها: **{r['station_count']}**\n"
        text += f"- تعداد رکوردها: **{r['record_count']:,}**\n"
        
        return {'text': text, 'type': 'kpi', 'data': r}
    
    def _handle_forecast(self, entities: Dict) -> Dict:
        days = min(entities.get('number', 7), 30)
        query = """
            SELECT day, point_forecast, lower_95, upper_95
            FROM forecast_results WHERE day <= ? ORDER BY day
        """
        results = self._execute_safe_query(query, (days,))
        
        if not results:
            return {'text': 'پیش‌بینی در دسترس نیست.', 'type': 'error'}
        
        total = sum(r['point_forecast'] for r in results)
        avg = total / len(results)
        
        text = f"🔮 **پیش‌بینی {days} روز آینده:**\n\n"
        text += f"- میانگین: **{avg:,.0f}** واحد در روز\n"
        text += f"- مجموع: **{total:,.0f}** واحد\n\n📈 **جزئیات:**\n"
        for r in results[:7]:
            text += f"- روز {r['day']}: **{r['point_forecast']:,.0f}** (بازه: {r['lower_95']:,.0f} - {r['upper_95']:,.0f})\n"
        
        return {'text': text, 'type': 'forecast', 'data': results, 'visualization': 'line'}
    
    def _handle_scenario(self, entities: Dict) -> Dict:
        query = """
            SELECT scenario_name, temp_change, change_pct, total_diff
            FROM scenario_summary ORDER BY temp_change
        """
        results = self._execute_safe_query(query)
        
        if not results:
            return {'text': 'سناریوها در دسترس نیستند.', 'type': 'error'}
        
        text = "🎯 **تحلیل سناریوهای دمایی:**\n\n"
        for r in results:
            emoji = "❄️" if r['temp_change'] < 0 else "🔥" if r['temp_change'] > 0 else "🌡️"
            text += f"- {emoji} **{r['scenario_name']}** ({r['temp_change']:+d}°C): تغییر **{r['change_pct']:+.2f}٪**\n"
        
        critical = max(results, key=lambda x: abs(x['temp_change']))
        text += f"\n⚠️ **هشدار:** در شرایط '{critical['scenario_name']}'، مصرف **{abs(critical['change_pct']):.1f}٪** تغییر می‌کند."
        
        return {'text': text, 'type': 'scenario', 'data': results}
    
    def _handle_anomalies(self, entities: Dict) -> Dict:
        query = """
            SELECT shamsi_year, shamsi_month, shamsi_day, نام_ایستگاه, استان,
                   اختلاف_دمای_ساعت_6_صبح
            FROM station_consumption_daily
            WHERE اختلاف_دمای_ساعت_6_صبح IS NOT NULL
              AND ABS(اختلاف_دمای_ساعت_6_صبح) > 100
            ORDER BY ABS(اختلاف_دمای_ساعت_6_صبح) DESC LIMIT 5
        """
        results = self._execute_safe_query(query)
        
        if not results:
            return {'text': '✅ ناهنجاری عمده‌ای کشف نشده است.', 'type': 'success'}
        
        text = f"⚠️ **{len(results)} ناهنجاری کشف شده:**\n\n"
        for i, r in enumerate(results, 1):
            date = f"{r['shamsi_year']}/{r['shamsi_month']:02d}/{r['shamsi_day']:02d}"
            text += f"{i}. **{r['نام_ایستگاه']}** ({r['استان']}) - {date}: اختلاف **{r['اختلاف_دمای_ساعت_6_صبح']:.1f}** درجه\n"
        
        return {'text': text, 'type': 'anomaly', 'data': results}
    
    def _handle_top_stations(self, entities: Dict) -> Dict:
        limit = min(entities.get('top_n', 5), 20)
        query = """
            SELECT نام_ایستگاه, استان, SUM(میزان_مصرف) as total_consumption
            FROM station_consumption_daily WHERE نام_ایستگاه IS NOT NULL
            GROUP BY نام_ایستگاه, استان ORDER BY total_consumption DESC LIMIT ?
        """
        results = self._execute_safe_query(query, (limit,))
        
        if not results:
            return {'text': 'داده‌ای یافت نشد.', 'type': 'error'}
        
        text = f"🏆 **{limit} ایستگاه پرمصرف:**\n\n"
        for i, r in enumerate(results, 1):
            text += f"{i}. **{r['نام_ایستگاه']}** ({r['استان']}): {r['total_consumption']:,.0f}\n"
        
        return {'text': text, 'type': 'table', 'data': results}
    
    def _handle_model_performance(self, entities: Dict) -> Dict:
        query = "SELECT model_name, MAE, RMSE, sMAPE, is_best FROM model_benchmarks ORDER BY MAE"
        results = self._execute_safe_query(query)
        
        if not results:
            return {'text': 'اطلاعات بنچمارک در دسترس نیست.', 'type': 'error'}
        
        best = next((r for r in results if r['is_best']), results[0])
        
        text = f"🏆 **بهترین مدل: {best['model_name']}**\n\n"
        text += f"📊 **معیارها:**\n- MAE: **{best['MAE']:,.0f}**\n- RMSE: **{best['RMSE']:,.0f}**\n- sMAPE: **{best['sMAPE']:.2f}٪**\n\n"
        text += "📋 **مقایسه:**\n"
        for i, r in enumerate(results, 1):
            badge = " 🏆" if r['is_best'] else ""
            text += f"{i}. {r['model_name']}{badge} - MAE: {r['MAE']:,.0f}\n"
        
        return {'text': text, 'type': 'model', 'data': results}
    
    def _handle_temperature_correlation(self, entities: Dict) -> Dict:
        query = "SELECT overall_correlation, interpretation, direction FROM temperature_impact_summary"
        results = self._execute_safe_query(query)
        
        if not results:
            return {'text': 'تحلیل اثر دما در دسترس نیست.', 'type': 'error'}
        
        r = results[0]
        corr = r['overall_correlation']
        
        text = f"🌡️ **رابطه دما و مصرف:**\n- **همبستگی:** {corr:.3f}\n"
        text += f"- **قدرت:** {r['interpretation']}\n- **جهت:** {r['direction']}\n\n"
        
        if abs(corr) < 0.1:
            text += "💡 **تفسیر:** رابطه بسیار ضعیف."
        elif abs(corr) < 0.3:
            text += "💡 **تفسیر:** رابطه ضعیف."
        else:
            text += "💡 **تفسیر:** رابطه متوسط تا قوی."
        
        return {'text': text, 'type': 'correlation', 'data': r}
    
    def _handle_total_consumption(self, entities: Dict) -> Dict:
        query = """
            SELECT SUM(میزان_مصرف) as total, COUNT(*) as records,
                   MIN(gregorian_date) as min_date, MAX(gregorian_date) as max_date
            FROM station_consumption_daily
        """
        results = self._execute_safe_query(query)
        
        if not results:
            return {'text': 'داده‌ای یافت نشد.', 'type': 'error'}
        
        r = results[0]
        text = f"📊 **کل مصرف گاز:**\n- **مجموع:** {r['total']:,.0f} واحد\n"
        text += f"- **رکوردها:** {r['records']:,}\n- **بازه:** {r['min_date']} تا {r['max_date']}\n"
        
        return {'text': text, 'type': 'kpi', 'data': r}
    
    def _handle_unknown(self, question: str) -> Dict:
        return {
            'text': (
                "🤔 متوجه نشدم. می‌توانم کمک کنم:\n\n"
                "1. 🏆 **پرمصرف‌ترین استان‌ها**\n"
                "2. 📊 **مصرف یک استان**\n"
                "3. 🔮 **پیش‌بینی**\n"
                "4. 🌡️ **سناریو دمایی**\n"
                "5. ⚠️ **ناهنجاری‌ها**\n"
                "6. 🤖 **بهترین مدل**\n"
                "7. 📈 **رابطه دما-مصرف**\n"
                "8. 📊 **کل مصرف**"
            ),
            'type': 'help'
        }
    
    def ask(self, question: str) -> Dict[str, Any]:
        if question.isdigit():
            idx = int(question) - 1
            if 0 <= idx < len(self.sample_questions):
                question = self.sample_questions[idx]
        
        clean_question = self._clean_text(question)
        intent = self._detect_intent(clean_question)
        entities = self._extract_entities(clean_question)
        
        self.conversation_context['last_question'] = question
        self.conversation_context['last_intent'] = intent
        self.conversation_context['last_entities'] = entities
        
        handler_map = {
            'top_consumption_provinces': self._handle_top_provinces,
            'province_consumption': self._handle_province_consumption,
            'forecast': self._handle_forecast,
            'temperature_scenario': self._handle_scenario,
            'anomalies': self._handle_anomalies,
            'top_stations': self._handle_top_stations,
            'model_performance': self._handle_model_performance,
            'temperature_correlation': self._handle_temperature_correlation,
            'total_consumption': self._handle_total_consumption,
        }
        
        handler = handler_map.get(intent, lambda entities: self._handle_unknown(clean_question))
        response = handler(entities)
        
        response['intent'] = intent
        response['question'] = question
        response['timestamp'] = datetime.now().isoformat()
        
        return response


def main():
    print("=" * 60)
    print("🤖 Gas AI Assistant - حالت تست")
    print("=" * 60)
    print("برای خروج 'quit' را وارد کنید\n")
    
    assistant = GasAIAssistant()
    
    print("📋 نمونه سؤالات:\n")
    for i, q in enumerate(assistant.sample_questions, 1):
        print(f"{i}. {q}")
    
    print("\n" + "=" * 60)
    
    while True:
        try:
            question = input("\n❓ سؤال شما: ").strip()
            if question.lower() in ['quit', 'exit', 'خروج']:
                break
            if not question:
                continue
            
            print("\n🤔 در حال پردازش...\n")
            response = assistant.ask(question)
            print("=" * 60)
            print(response['text'])
            print("=" * 60)
            print(f"[Intent: {response['intent']} | Type: {response['type']}]")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ خطا: {e}")


if __name__ == "__main__":
    main()