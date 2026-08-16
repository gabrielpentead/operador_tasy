#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cria um ícone simples para o aplicativo
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    
    # Criar uma imagem 256x256 com fundo azul
    img = Image.new('RGBA', (256, 256), (65, 105, 225, 255))  # Royal Blue
    draw = ImageDraw.Draw(img)
    
    # Desenhar círculo branco no centro
    circle_margin = 40
    circle_coords = [circle_margin, circle_margin, 256-circle_margin, 256-circle_margin]
    draw.ellipse(circle_coords, fill=(255, 255, 255, 255), outline=(200, 200, 200, 255), width=4)
    
    # Adicionar texto "T" no centro
    try:
        # Tentar usar fonte do sistema
        font_size = 120
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Usar fonte padrão se arial não estiver disponível
        font = ImageFont.load_default()
    
    text = "T"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_x = (256 - text_width) // 2
    text_y = (256 - text_height) // 2 - 10  # Ajuste para centralizar melhor
    
    draw.text((text_x, text_y), text, fill=(65, 105, 225, 255), font=font)
    
    # Salvar como ICO
    img.save('app.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    print("✅ Ícone criado: app.ico")
    
except ImportError:
    print("⚠️ PIL não disponível. Criando ícone vazio...")
    # Criar um arquivo ICO mínimo válido
    ico_data = bytes([
        0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x20, 0x20, 0x00, 0x00, 0x01, 0x00, 0x20, 0x00, 0x30, 0x25,
        0x00, 0x00, 0x16, 0x00, 0x00, 0x00, 0x28, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x40, 0x00,
        0x00, 0x00, 0x01, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    ])
    
    # Preencher com dados de pixel azuis (simplificado)
    ico_data += b'\x41\x69\xe1\xff' * (32 * 32)  # 32x32 pixels azuis
    ico_data += b'\x00' * (32 * 4)  # Máscara AND
    
    with open('app.ico', 'wb') as f:
        f.write(ico_data)
    print("✅ Ícone básico criado: app.ico")

except Exception as e:
    print(f"❌ Erro ao criar ícone: {e}")
    print("Continuando build sem ícone...")
