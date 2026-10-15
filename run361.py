import sys, pathlib
sys.path.insert(0, '/tmp/claude-0/-home-claude/b70105c3-e941-5e93-a2e0-04556ffb5bee/scratchpad/v361')
import core
meta = dict(etablissement="Complexe Scolaire Francisco Palau", eleve="Test Élève", classe="6e littéraire",
            matiere="Géographie", titulaire="Encadreur Test", theme="L'histoire de la RDC", annee="2026-2027", date="12/10/2026")
text = open(sys.argv[1], encoding='utf-8').read()
pack, sommaire, police = sys.argv[2], sys.argv[3], sys.argv[4]
pdf = core.build_pdf(pack, meta, text, sommaire=sommaire, police=police)
out = pathlib.Path(sys.argv[5]); out.write_bytes(pdf); print("ok", out, len(pdf))
