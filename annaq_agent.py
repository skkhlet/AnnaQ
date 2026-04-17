"""
عنّاق — AI Agent
==================
مع دمج كامل للـ Recommender (LinUCB)

pip install groq python-dotenv numpy

=============================================================
📝 آخر تعديلات (لفريق العمل):
=============================================================
أصلحت ربط الـ Recommender مع الفرنت إند:

1. نقل get_last_recommendations و give_feedback داخل الكلاس
   (كانوا خارجها فما يشتغلوا مع web_app.py)

2. get_last_recommendations يرجع بيانات كاملة من CSV:
   اسم، صورة، وصف، تقييم، خرايط، highlights
   (كان يرجع بس id و name)

3. _handle_feedback يعطي تفاصيل المكان المختار
   (بدل "شكراً!" فقط)

4. إضافة load_place_details لقراءة كل حقول CSV

# flow المحادثة (4 مسارات):
# 1) وداع → رد ثابت
# 2) اختار رقم → تحديث bandit + تفاصيل المكان
# 3) طلب توصية → LinUCB يرجع 5 أماكن
# 4) محادثة عادية → LLM
=============================================================
"""

import os
import json #للتخزين المؤقت للبيانات . by skh
import pickle #by skh
import csv
from dotenv import load_dotenv
load_dotenv()

from groq import Groq
from recommender.preference_vector import preferences_to_vector
from recommender.linucb import LinUCB
from recommender.place_vector import load_places_with_vectors


CSV_PATH = os.path.join(os.path.dirname(__file__), 'places.csv')
BANDIT_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'bandit_model.pkl')


def load_place_details(csv_path=CSV_PATH):
    """حمّل كل معلومات الأماكن من CSV كـ dict {place_id: {...}}."""
    details = {}
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row['place_id']
            details[pid] = {
                'id': pid,
                'name': row.get('name_ar', ''),
                'name_en': row.get('name_en', ''),
                'city': row.get('city', ''),
                'district': row.get('district', ''),
                'type': row.get('primary_type', ''),
                'category': row.get('category', ''),
                'budget': row.get('budget', ''),
                'rating': row.get('rating', ''),
                'description': row.get('description_ar', ''),
                'highlights': row.get('highlights', ''),
                'tags': row.get('tags', ''),
                'indoor_outdoor': row.get('indoor_outdoor', ''),
                'family_friendly': row.get('family_friendly', ''),
                'best_time': row.get('best_time_of_day', ''),
                'duration_hours': row.get('duration_hours', ''),
                'latitude': row.get('latitude', ''),
                'longitude': row.get('longitude', ''),
                'maps_url': row.get('google_maps_url', ''),
                'website': row.get('website', ''),
                'image': row.get('image_url', '') or '',
                'phone': row.get('phone_number', ''),
            }
    return details


ANNAQ_PERSONALITY = """أنت عنّاق، رفيق رقمي سعودي ذكي ولطيف. شخصيتك مستوحاة من حيوان الوشق (عنّاق الأرض).

## شخصيتك:
- تتكلم لهجة سعودية بيضاء مفهومة للكل
- لطيف وحماسي بس طبيعي ومو مبالغ
- فخور بالسعودية وتحب تحكي عن أماكنها
- تكلم بطبيعية مثل ما تسولف مع صاحبك

## ممنوعات لغوية (مهم):
- أنت سعودي ولا تستخدم أي كلمة مصرية.
- كلمات ممنوعة ← البديل السعودي:
  "كمان" ← "بعد"
  "بتحب" ← "تحب"
  "عايز" ← "أبي"
  "حاجة" ← "شيء"
  "دلوقتي" ← "الحين"
  "متتنسيش" ← "ما تنتسى"

## أمثلة ترحيب طبيعية:
- "هلا والله! أنا عنّاق، وش تبي تسوي اليوم؟"
- "أهلاً فيك! تبي نستكشف أماكن حلوة بالسعودية؟"
- "حياك الله! قولي وش يهمك وأنا أساعدك"

## مهمتك:
- تساعد الزوار يكتشفون أماكن سياحية بالسعودية
- تعطي توصيات شخصية من قاعدة البيانات
- تحكي عن تاريخ وثقافة الأماكن

## قواعد:
- ردودك قصيرة (3-4 جمل)
- لا تستخدم إيموجي
- إذا الزائر طلب توصية، النظام بيوصّي له تلقائياً

## الوداع:
- "الله يسعدك! إن شاء الله نشوفك مرة ثانية"
"""


class AnnaqAgent:

    DIALECT_FIXES = {
        "كمان": "بعد",
        "بتحب": "تحب",
        "بتبي": "تبي",
        "عايز": "أبي",
        "عاوز": "أبي",
        "حاجة": "شيء",
        "دلوقتي": "الحين",
        "كده": "كذا",
        "بتاع": "حق",
        "ازيك": "كيف حالك",
        "متتنسيش": "ما تنتسى",
        "ماتنسيش": "ما تنتسى",
        "يارب": "إن شاء الله",
        "أكتر": "أكثر",
        "تانية": "ثانية",
        "تاني": "ثاني",
        "تعمل": "تسوي",
        "نعمل": "نسوي",
        "أعمل": "أسوي",
        "إزاي": "كيف",
        "فين": "وين",
    }

    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        self.history = [
            {"role": "system", "content": ANNAQ_PERSONALITY}
        ]

#what's below here is new .by skh
    # ======== تحميل بيانات الأماكن ونظام التوصيات ========
        try:
            place_ids, place_names, _, place_vectors_36 = load_places_with_vectors(CSV_PATH)
            self.place_ids = place_ids
            self.place_names = place_names
            self.place_vectors_36 = place_vectors_36
            self.place_details = load_place_details(CSV_PATH)

            n_arms = len(place_ids)
            if os.path.exists(BANDIT_MODEL_PATH):
                with open(BANDIT_MODEL_PATH, 'rb') as f:
                    self.recommender = pickle.load(f)
                print(f"✅ تم تحميل نموذج التوصيات ({n_arms} مكان)")
            else:
                self.recommender = LinUCB(
                    n_arms, n_features=36, alpha=1.0,
                    arm_features=place_vectors_36, beta=0.5
                )
                print(f"✅ نموذج توصيات جديد ({n_arms} مكان)")

            self.last_context = None
            self.last_arm_indices = None

        except Exception as e:
            print(f"⚠️ فشل تحميل نظام التوصيات: {e}")
            self.recommender = None
            self.place_ids = []
            self.place_names = {}
            self.place_details = {}
            self.last_context = None
            self.last_arm_indices = None
#what's above here is new .by skh

    def _fix_dialect(self, text: str) -> str:
        for eg, sa in self.DIALECT_FIXES.items():
            text = text.replace(eg, sa)
        return text

#what's below here is new .by skh
#استخراج التفضيلات من حديث الزائر

    def extract_preferences(self, user_message: str) -> dict:
        """استخراج تفضيلات الزائر من كلامه."""
        prompt = f"""استخرج من كلام الزائر JSON فقط بدون أي نص إضافي.

الحقول الممكنة:
- primary_type: attraction, restaurant, cafe, mall, park, religious
- budget: low, medium, high, luxury
- family_friendly: true/false
- indoor_outdoor: indoor, outdoor, either
- cuisine: saudi, lebanese, american, seafood, italian, japanese, turkish, none
- best_time: morning, evening, anytime
- weather_sensitive_ok: true/false

إذا ما ذكر الزائر شيء، لا تضمنه.

كلام الزائر: "{user_message}"

JSON:"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()

            # تنظيف markdown
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            prefs = json.loads(content)

            for key in ['family_friendly', 'weather_sensitive_ok']:
                if key in prefs and isinstance(prefs[key], str):
                    prefs[key] = prefs[key].lower() == 'true'

            return prefs
        except Exception as e:
            print(f"⚠️ فشل استخراج التفضيلات: {e}")
            return {}
#what's above here is new .by skh

    def _is_recommendation_request(self, message: str) -> bool:
        keywords = [
            "اقترح", "وين أروح", "أبي مطعم", "أبي مكان", "دلني",
            "وش الأماكن", "اقتراح", "توصية", "وين نروح", "رشح",
            "فكرة", "ممكن مكان", "تنصحني", "أفضل مكان"
        ]
        return any(kw in message for kw in keywords)

    def _is_feedback_response(self, message: str):
        """رجع رقم المكان اللي اختاره الزائر (1-5) أو None."""
        if self.last_arm_indices is None:
            return None

        num_words = {
            "الأول": 1, "أول": 1, "1": 1, "واحد": 1,
            "الثاني": 2, "ثاني": 2, "2": 2, "اثنين": 2,
            "الثالث": 3, "ثالث": 3, "3": 3, "ثلاثة": 3,
            "الرابع": 4, "رابع": 4, "4": 4, "أربعة": 4,
            "الخامس": 5, "خامس": 5, "5": 5, "خمسة": 5,
        }

        for word, num in num_words.items():
            if word in message and num <= len(self.last_arm_indices):
                return num
        return None

    def _recommend(self, user_message: str):
        """أعطي توصيات بناءً على كلام الزائر."""
        prefs = self.extract_preferences(user_message)
        if not prefs:
            return None

        context = preferences_to_vector(prefs, gender=None, expression=None)
        arm_indices, scores = self.recommender.get_recommendations(context, top_k=5)

        self.last_context = context
        self.last_arm_indices = arm_indices

        reply = "تمام! بناءً على اللي قلته، أقترح عليك:\n"
        for i, idx in enumerate(arm_indices):
            pid = self.place_ids[idx]
            name = self.place_names.get(pid, pid)
            reply += f"{i+1}. {name}\n"
        reply += "\nقول لي رقم اللي عجبك عشان أعطيك تفاصيله."
        return reply

    def _handle_feedback(self, chosen_num: int) -> str:
        """الزائر اختار توصية، حدّث النموذج وأعطي تفاصيل."""
        chosen_arm = self.last_arm_indices[chosen_num - 1]

        self.recommender.update(chosen_arm, self.last_context, reward=1.0)

        try:
            with open(BANDIT_MODEL_PATH, 'wb') as f:
                pickle.dump(self.recommender, f)
        except Exception as e:
            print(f"⚠️ فشل حفظ النموذج: {e}")

        pid = self.place_ids[chosen_arm]
        place = self.place_details.get(pid, {})
        name = place.get('name', pid)
        desc = place.get('description', '')
        highlights = place.get('highlights', '')

        self.last_context = None
        self.last_arm_indices = None

        reply = f"اختيار موفق! {name}"
        if desc:
            short_desc = desc[:200] + "..." if len(desc) > 200 else desc
            reply += f"\n\n{short_desc}"
        if highlights:
            reply += f"\n\nأبرز المميزات: {highlights}"
        reply += "\n\nتبي أقترح عليك مكان ثاني؟"
        return reply

    def chat(self, user_message: str) -> str:
        # 1. وداع
        bye_words = ["مع السلامة", "مع السلامه", "سلام عليكم", "يلا باي", "باي"]
        if any(word in user_message for word in bye_words):
            reply = "الله يسعدك! إن شاء الله نشوفك مرة ثانية."
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": reply})
            return reply

        # 2. رد على توصية سابقة
#what's below here is new .by skh
        if self.recommender and self.last_arm_indices is not None:
            chosen = self._is_feedback_response(user_message)
            if chosen is not None:
                reply = self._handle_feedback(chosen)
                self.history.append({"role": "user", "content": user_message})
                self.history.append({"role": "assistant", "content": reply})
                return reply

        # 3. طلب توصية
        if self.recommender and self._is_recommendation_request(user_message):
            reply = self._recommend(user_message)
            if reply:
                self.history.append({"role": "user", "content": user_message})
                self.history.append({"role": "assistant", "content": reply})
                return reply
#what's above here is new .by skh

        # 4. محادثة عادية
        self.history.append({"role": "user", "content": user_message})
        messages = [self.history[0]] + self.history[-20:]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=300,
        )

        reply = response.choices[0].message.content.strip()
        reply = self._fix_dialect(reply)
        self.history.append({"role": "assistant", "content": reply})
        return reply

#added by skh
    def get_last_recommendations(self) -> list:
        """ارجع آخر توصيات بمعلومات كاملة (للفرنت إند)."""
        if self.last_arm_indices is None or len(self.last_arm_indices) == 0:
            return []
        recs = []
        for arm_idx in self.last_arm_indices:
            pid = self.place_ids[arm_idx]
            place = self.place_details.get(pid, {})
            recs.append({
                'id': pid,
                'name': place.get('name', pid),
                'name_en': place.get('name_en', ''),
                'city': place.get('city', ''),
                'description': place.get('description', '')[:200],
                'rating': place.get('rating', ''),
                'image': place.get('image', ''),
                'maps_url': place.get('maps_url', ''),
                'type': place.get('type', ''),
                'highlights': place.get('highlights', ''),
            })
        return recs

    def give_feedback(self, place_id: str, reward: float = 1.0):
        """تحديث النموذج بـ feedback من الفرنت إند."""
        if self.last_context is None or self.last_arm_indices is None:
            return False
        try:
            arm_idx = self.place_ids.index(place_id)
        except ValueError:
            return False
        if arm_idx not in self.last_arm_indices:
            return False

        self.recommender.update(arm_idx, self.last_context, reward=reward)
        try:
            with open(BANDIT_MODEL_PATH, 'wb') as f:
                pickle.dump(self.recommender, f)
        except Exception as e:
            print(f"⚠️ فشل حفظ النموذج: {e}")

        self.last_context = None
        self.last_arm_indices = None
        return True

    def reset(self):
        self.history = [
            {"role": "system", "content": ANNAQ_PERSONALITY}
        ]
        self.last_context = None #by skh
        self.last_arm_indices = None #by skh


if __name__ == "__main__":
    if not os.environ.get("GROQ_API_KEY"):
        print("❌ سوّ ملف .env واكتب فيه: GROQ_API_KEY=gsk_مفتاحك")
        exit(1)

    agent = AnnaqAgent()

    print("=" * 40)
    print("  عنّاق — رفيقك السياحي")
    print("=" * 40)

    while True:
        user_input = input("\nأنت: ").strip()

        if user_input in ["خروج", "exit", "q"]:
            print("عنّاق: الله يسعدك!")
            break

        if user_input in ["جديد", "new", "reset"]:
            agent.reset()
            print("بدأنا محادثة جديدة!")
            continue

        if not user_input:
            continue

        reply = agent.chat(user_input)
        print(f"\nعنّاق: {reply}")

        recs = agent.get_last_recommendations()
        if recs:
            print(f"\n[{len(recs)} توصية جاهزة للفرنت إند]")

        if any(word in reply for word in ["السلامة", "يحفظك", "نشوفك"]):
            break
