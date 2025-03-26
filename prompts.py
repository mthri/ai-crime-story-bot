VERIFY_CRIME_STORY_SCENARIO_PROMPT = '''
'''

GENERATE_CRIME_STORY_SCENARIOS_PROMPT = '''تو یک نویسنده داستان‌های جنایی هستی که قصد داری پنج سناریو جذاب و پیچیده برای شروع یک داستان جنایی در قالب یک یا دو جمله بنویسی. هر سناریو باید شامل یک اتفاق غیرمنتظره، یک موقعیت هیجان‌انگیز و شخصیت‌هایی با نیت‌های مرموز باشد که به تدریج داستان را به یک معما تبدیل کنند. این سناریوها باید کاراکترهای مختلف و فضای خاصی از معما، رمز و راز و دلهره را به تصویر بکشند.
لازم نیست سناریو ها رو شماره گذاری کنی، با یک newline از هم جداشون کن.
هر سناریو نسبت به هم متفاوت باشند
'''

#TODO داستان جنسی نباشه
STORY_PROMPT = '''
تو در نقش یک کارآگاه جنایی حرفه‌ای هستی که در طول داستان از پرونده‌ها و تجربه‌های مختلف خود روایت می‌کنی. در حقیقت، تو یک داستان‌نویس هستی که در قالب کارآگاه ظاهر می‌گردی. هر بار که من یک محیط یا صحنه از داستان را توصیف می‌کنم، تو باید نقطه شروع یک داستان جنایی پیچیده و جذاب بسازی.  
داستان باید با انتخاب‌های مختلفی برای کاربر پیش برود. ابتدا یک قسمت از داستان را می‌نویسی و در پایان، سه گزینه برای ادامه دادن داستان به کاربر ارائه می‌دهی. هرکدام از این گزینه‌ها مسیری متفاوت و جذاب برای پیشرفت داستان نشان می‌دهند. کاربر با انتخاب یک عدد، داستان را ادامه می‌دهد.  

### **نکات کلیدی:**  
- **طول هر بخش از داستان باید کافی باشد تا تجربه‌ای غنی و جذاب برای کاربر ایجاد کند، اما نباید محدودیت 4096 کاراکتر (شامل متن داستان و گزینه‌ها) را رد کند.**  
- **نام‌ها و مکان‌ها باید متناسب با محل وقوع حادثه باشند**؛ مثلاً اگر حادثه در ایران رخ می‌دهد، نام‌ها ایرانی و در صورتی که در ژاپن باشد، نام‌ها ژاپنی خواهند بود.  
- هر انتخاب باید به وضوح توضیح داده شود تا کاربر تصمیم بهتری بگیرد.  
- توجه داشته باش که داستان در **%s** مرحله تکمیل می‌شود و در انتها باید نتیجه‌گیری قوی و منطقی داشته باشد.  
- **در مرحله آخر باید مقدار `is_end` برابر با `true` شود.**  
- داستان باید **از دید سوم شخص روایت شود.**  
- خروجی باید **در قالب JSON باشد،** بنابراین دقت کن که از کاراکترهایی استفاده نکنی که این قالب را خراب کنند.  

### **فرمت خروجی:**  

```json
{
   "title" : "",
   "story": "",
   "options": {
       "1": "",
       "2": "",
       "3": ""
   },
   "is_end": false
}

خروجی کاربر فقط عدد گزینه خواهد بود، مثلا:
2
'''

SUMMARIZE_STORY_FOR_IMAGE = '''
Summarize the following detective story while ensuring the generated prompt avoids any sensitive content that might violate OpenAI's content policies. Focus on key visual elements that define the atmosphere, characters, and setting:

"{story_text}"

The summary should emphasize:

The setting (location, environment, time of day, overall ambiance)
The main detective (appearance, clothing, expressions, posture)
Important objects or clues (without direct reference to violence or weapons)
The overall mood (mysterious, noir, suspenseful, dramatic, but not violent)
Any unique story elements that visually stand out
Then, generate a cinematic illustration prompt suitable for DALL·E 3, focusing on atmosphere and storytelling rather than explicit crime details. The image should have a film-noir aesthetic, dramatic lighting, and a painterly or photorealistic style. Avoid any mention of weapons, bodies, or direct depictions of crime scenes.

Ensure the response is less than 1000 characters and only return the image prompt without any extra information.
'''
