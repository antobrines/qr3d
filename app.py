import os
import uuid
import qrcode
import cadquery as cq
from flask import Flask, request, render_template, send_file, jsonify
from PIL import Image
from pyzbar.pyzbar import decode

app = Flask(__name__)
UPLOAD_FOLDER = '/tmp/qr_3d'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate_preview', methods=['POST'])
def generate_preview():
    # --- 1. Gestion du contenu (Texte ou Image) ---
    qr_content = request.form.get('url_content')

    if 'qr_file' in request.files and request.files['qr_file'].filename != '':
        try:
            img = Image.open(request.files['qr_file'].stream)
            decoded = decode(img)
            if decoded:
                qr_content = decoded[0].data.decode('utf-8')
            else:
                return jsonify({"error": "Impossible de lire le QR code"}), 400
        except Exception as e:
            return jsonify({"error": f"Erreur image: {str(e)}"}), 400

    if not qr_content:
        return jsonify({"error": "Veuillez fournir une URL ou une image"}), 400

    # --- 2. Paramètres ---
    back_text = request.form.get('back_text', '')
    thickness = float(request.form.get('thickness', 3.0))
    add_hole = request.form.get('add_hole') == 'true'
    hole_radius = float(request.form.get('hole_radius', 2.5))  # optionnel (non exposé UI)
    mode = request.form.get('mode', 'relief')
    qr_height = float(request.form.get('qr_height', 1.0))      # optionnel (non exposé UI)

    unique_id = str(uuid.uuid4())
    stl_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}.stl")

    try:
        # --- 3. Matrice QR ---
        qr = qrcode.QRCode(version=1, box_size=1, border=0)
        qr.add_data(qr_content)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        size = len(matrix)

        # --- 4. Dimensions base ---
        padding = 6  # en "modules"
        base_w = size + padding

        margin_around_hole = 5.0
        extra_top = (hole_radius * 2.0) + margin_around_hole if add_hole else 0.0

        base_h = base_w + extra_top

        # --- 5. Base (centrée) ---
        model = cq.Workplane("XY").box(base_w, base_h, thickness)

        # --- 6. Gravure dos ---
        if back_text:
            model = model.faces("<Z").workplane(centerOption="CenterOfBoundBox") \
                .text(back_text, 5, -0.4, font="Arial", kind="bold")

        # --- 7. Placement QR (centré dans la zone utile sous le trou) ---
        qr_center_x = 0.0
        qr_center_y = -extra_top / 2.0  # centre de la zone utile (sous le trou)

        qr_origin_x = qr_center_x - (size / 2.0) + 0.5
        qr_origin_y = qr_center_y - (size / 2.0) + 0.5

        points = []
        for r, row in enumerate(matrix):
            for c, pixel in enumerate(row):
                if pixel:
                    x = qr_origin_x + c
                    y = qr_origin_y + (size - 1 - r)
                    points.append((x, y))

        # --- 8. Appliquer QR SUR LA FACE DU DESSUS DU MODÈLE ---
        top_wp = model.faces(">Z").workplane(centerOption="CenterOfBoundBox")
        if mode == 'inlay':
            final_model = top_wp.pushPoints(points).rect(0.95, 0.95).cutBlind(-qr_height)
        else:
            final_model = top_wp.pushPoints(points).rect(1.0, 1.0).extrude(qr_height)

        # --- 9. Trou (FAIRE LE TROU SUR final_model, PAS sur model) ---
        if add_hole:
            dist_from_top = hole_radius + 2.5
            hole_y_pos = (base_h / 2.0) - dist_from_top

            # Z du dessus (pour être au-dessus du solide dans les 2 modes)
            top_z = (thickness / 2.0) + (qr_height if mode == "relief" else 0.0)

            # Cylindre "cutter" créé en repère global XY et extrudé vers le bas largement
            cutter = (
                cq.Workplane("XY")
                .workplane(offset=top_z + 1.0)          # 1mm au-dessus du top
                .center(0, hole_y_pos)
                .circle(hole_radius)
                .extrude(-(thickness + qr_height + 10)) # traverse tout, marge 10mm
            )

            final_model = final_model.cut(cutter)

        # --- 10. Export ---
        cq.exporters.export(final_model, stl_path)

        return jsonify({"qr_content": qr_content, "stl_url": f"/download_stl/{unique_id}.stl"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download_stl/<filename>')
def download_stl(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
