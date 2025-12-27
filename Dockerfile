FROM mambaorg/micromamba:latest

USER root
RUN apt-get update && apt-get install -y \
    libzbar0 libgl1 libglx-mesa0 fonts-freefont-ttf \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation de la stack
RUN micromamba install -y -n base -c cadquery -c conda-forge \
    python=3.10 cadquery flask qrcode pillow pyzbar && \
    micromamba clean --all --yes

COPY . .

# IMPORTANT : On s'assure que le dossier temporaire a les bons droits
RUN mkdir -p /tmp/qr_3d && chmod -R 777 /tmp/qr_3d

EXPOSE 5000

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh"]
CMD ["python", "app.py"]