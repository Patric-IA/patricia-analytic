# Usa una imagen base de Python
FROM python:3.10-slim

# Define el directorio de trabajo
WORKDIR /app

# Copia los archivos de dependencias
COPY requirements.txt .

RUN apt-get update && apt-get install -y ffmpeg

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación al contenedor
COPY . .

# Expone el puerto en el que correrá FastAPI
EXPOSE 8000

# Comando para iniciar la aplicación FastAPI con Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
