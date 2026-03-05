# Usar una imagen base ligera de Python
FROM python:3.9-slim

# Establecer el directorio de trabajo en el contenedor
WORKDIR /app

# Copiar el archivo de requisitos y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del backend y la conexión a la DB
COPY . .

# Exponer el puerto en el que correrá uvicorn (interno del contenedor)
EXPOSE 8000

# Comando para ejecutar la aplicación
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
