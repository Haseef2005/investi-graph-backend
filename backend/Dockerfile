# Dockerfile

# 1. Base Image: ใช้ Image Python 3.11 (Slim คือเบาๆ)
FROM python:3.11-slim

# 2. Set Working Directory: บอกว่าโค้ดเราจะอยู่ใน /app
WORKDIR /app

# "เพิ่มบรรทัดนี้" -> บอก Python ว่าให้ "มองหา" code ที่ "ราก" (/app) ด้วย
ENV PYTHONPATH=/app

# 3. Copy Dependencies: ก๊อป "ใบรายการ" เข้าไปก่อน
#    (เราก๊อปแค่ 2 ไฟล์นี้ก่อน เพื่อใช้ "Layer Caching" ของ Docker)
#    (ถ้า requirements ไม่เปลี่ยน Docker จะไม่ลงใหม่ ประหยัดเวลา)
COPY requirements.txt requirements.txt

# 4. Install Dependencies: ลง Library ทั้งหมด
#    (เราต้องมี argon2-cffi dependencies ก่อน)
RUN apt-get update && apt-get install -y libffi-dev gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove libffi-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy App Code: ก๊อปโค้ด "ทั้งหมด" ของเราเข้าไปใน /app
COPY . .

# 6. Expose Port: บอก Docker ว่าแอปเราจะรันที่ Port 8000
EXPOSE 8000

# 7. Command: คำสั่ง "เริ่ม" แอป (เราจะรันผ่าน uvicorn)
#    host=0.0.0.0 คือการบอกว่า "รับการเชื่อมต่อจากภายนอก Container ด้วย"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]