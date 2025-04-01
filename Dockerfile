FROM python:3.9-slim

WORKDIR /usr/src/app

# Copy only requirements first
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code (but NOT the Excel files)
COPY app.py . 

EXPOSE 5001

CMD ["python", "app.py"]