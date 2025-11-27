from google import genai
from PIL import Image
import base64
import io

client = genai.Client()

prompt = (
    "أنشئ صورة واقعية وحساسة تُظهر معاناة الشعب الفلسطيني، "
    "تركز على المشاعر والصمود والإنسانية، "
    "بطريقة فنية محترمة."
)

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[prompt],
)

for part in response.parts:
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        try:
            # محاولة استخدام as_image مباشرة
            image = part.as_image()
            if image:
                image.save("image.png", format="PNG")
                print("تم حفظ الصورة!")
        except Exception as e:
            print(f"خطأ في حفظ الصورة: {e}")
            # محاولة بديلة
            image_bytes = part.inline_data.data
            with open("image.png", "wb") as f:
                f.write(image_bytes)
            print("تم حفظ الصورة كبيانات خام")