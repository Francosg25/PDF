# -*- coding: utf-8 -*-
"""
VisorPDF3000 Pro - Windows 10/11
Busca palabras y frases dentro del contenido de archivos PDF.
Incluye OCR opcional/automático para páginas escaneadas mediante Tesseract.
"""
import os, sys, sqlite3, subprocess, csv, shutil
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QAction
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QProgressBar, QComboBox, QCheckBox, QSplitter, QTextEdit,
    QSpinBox, QGroupBox, QMenu
)

APP_NAME = "VisorPDF3000 Pro"
ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA = ROOT / "Data"
DATA.mkdir(exist_ok=True)
DB_PATH = DATA / "catalogo.sqlite3"
CONFIG_PATH = DATA / "config.txt"

def read_config():
    cfg = {}
    if CONFIG_PATH.exists():
        for line in CONFIG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg

def write_config(cfg):
    CONFIG_PATH.write_text("\\n".join(f"{k}={v}" for k,v in cfg.items()), encoding="utf-8")

def db_connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS pdfs(
        id INTEGER PRIMARY KEY, path TEXT UNIQUE, name TEXT, size INTEGER,
        modified REAL, pages INTEGER, favorite INTEGER DEFAULT 0, category TEXT DEFAULT ''
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS page_text(
        pdf_id INTEGER, page_no INTEGER, content TEXT,
        PRIMARY KEY(pdf_id,page_no),
        FOREIGN KEY(pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_page_text_pdf ON page_text(pdf_id)")
    con.commit()
    return con

def locate_tesseract():
    cfg = read_config()
    candidates = [
        cfg.get("tesseract", ""),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    ]
    for p in candidates:
        if p and Path(p).exists():
            return p
    return shutil.which("tesseract") or ""

class IndexWorker(QThread):
    progress = Signal(int, int, str)
    finished_msg = Signal(str)
    def __init__(self, folder, use_ocr, lang):
        super().__init__()
        self.folder, self.use_ocr, self.lang = folder, use_ocr, lang
    def run(self):
        con = db_connect()
        files = list(Path(self.folder).rglob("*.pdf")) + list(Path(self.folder).rglob("*.PDF"))
        total = len(files)
        if not total:
            self.finished_msg.emit("No se encontraron archivos PDF en esa carpeta.")
            con.close(); return
        tess = locate_tesseract()
        if self.use_ocr and not tess:
            self.finished_msg.emit("No se encontró Tesseract. Instálalo y vuelve a indexar. Consulta LEEME.txt.")
            con.close(); return
        if tess:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = tess
                from PIL import Image
            except Exception:
                pytesseract = None
        else:
            pytesseract = None
        for i, path in enumerate(files, 1):
            try:
                st = path.stat()
                cur = con.execute("SELECT id,size,modified FROM pdfs WHERE path=?", (str(path),)).fetchone()
                if cur and cur[1] == st.st_size and cur[2] == st.st_mtime:
                    self.progress.emit(i, total, f"Sin cambios: {path.name}")
                    continue
                if cur:
                    pid = cur[0]
                    con.execute("DELETE FROM page_text WHERE pdf_id=?", (pid,))
                    con.execute("UPDATE pdfs SET name=?,size=?,modified=?,pages=0 WHERE id=?",
                                (path.name,st.st_size,st.st_mtime,pid))
                else:
                    c = con.execute("INSERT INTO pdfs(path,name,size,modified,pages) VALUES(?,?,?,?,0)",
                                    (str(path),path.name,st.st_size,st.st_mtime))
                    pid = c.lastrowid
                doc = fitz.open(path)
                for n, page in enumerate(doc, 1):
                    txt = page.get_text("text") or ""
                    # OCR solo para páginas sin texto útil; evita procesar de nuevo PDFs digitales.
                    if self.use_ocr and len(txt.strip()) < 8 and pytesseract:
                        try:
                            pix = page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
                            img = Image.frombytes("RGB", [pix.width,pix.height], pix.samples)
                            txt = pytesseract.image_to_string(img, lang=self.lang)
                        except Exception:
                            pass
                    con.execute("INSERT OR REPLACE INTO page_text(pdf_id,page_no,content) VALUES(?,?,?)",
                                (pid,n,txt))
                con.execute("UPDATE pdfs SET pages=? WHERE id=?", (len(doc),pid))
                doc.close()
                con.commit()
                self.progress.emit(i,total,f"Indexado: {path.name}")
            except Exception as e:
                self.progress.emit(i,total,f"Error en {path.name}: {e}")
        con.close()
        self.finished_msg.emit(f"Proceso terminado. Se revisaron {total} archivos PDF.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1250, 780)
        self.current_path = ""
        self.current_page = 1
        self.worker = None
        self.cfg = read_config()
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        self.folder = QLineEdit(self.cfg.get("folder",""))
        self.folder.setPlaceholderText("Carpeta que contiene tus PDF")
        btn_folder = QPushButton("Elegir carpeta")
        btn_folder.clicked.connect(self.choose_folder)
        btn_index = QPushButton("Indexar / actualizar PDF")
        btn_index.clicked.connect(self.start_index)
        top.addWidget(QLabel("Carpeta:")); top.addWidget(self.folder,1); top.addWidget(btn_folder); top.addWidget(btn_index)
        root.addLayout(top)

        search = QHBoxLayout()
        self.query = QLineEdit(); self.query.setPlaceholderText("Escribe una palabra, frase, número, nombre o apellido...")
        self.query.returnPressed.connect(self.search)
        btn_search = QPushButton("Buscar dentro de los PDF"); btn_search.clicked.connect(self.search)
        self.scope = QComboBox(); self.scope.addItems(["Todo el contenido","Nombre del archivo"])
        self.fav_only = QCheckBox("Solo favoritos")
        search.addWidget(self.query,1); search.addWidget(self.scope); search.addWidget(self.fav_only); search.addWidget(btn_search)
        root.addLayout(search)

        opts = QHBoxLayout()
        self.ocr = QCheckBox("Usar OCR en páginas escaneadas")
        self.ocr.setChecked(True)
        self.lang = QComboBox(); self.lang.addItems(["spa","eng","spa+eng"])
        opts.addWidget(self.ocr); opts.addWidget(QLabel("Idioma OCR:")); opts.addWidget(self.lang)
        opts.addWidget(QLabel("Categoría:"))
        self.category = QComboBox(); self.category.addItems(["Todas","Trabajo","Facturas","Personal","Legal","Otros"])
        opts.addWidget(self.category); opts.addStretch()
        root.addLayout(opts)

        split = QSplitter(Qt.Horizontal)
        self.results = QTreeWidget()
        self.results.setHeaderLabels(["Documento / página","Coincidencia"])
        self.results.setColumnWidth(0,270)
        self.results.setAlternatingRowColors(True)
        self.results.setRootIsDecorated(False)
        self.results.header().setStretchLastSection(True)
        self.results.itemDoubleClicked.connect(self.open_result)
        self.results.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self.context_menu)
        split.addWidget(self.results)

        preview = QWidget(); pv = QVBoxLayout(preview)
        nav = QHBoxLayout()
        self.info = QLabel("Selecciona un resultado para ver la página.")
        self.prev = QPushButton("◀ Página"); self.prev.clicked.connect(lambda:self.change_page(-1))
        self.next = QPushButton("Página ▶"); self.next.clicked.connect(lambda:self.change_page(1))
        self.zoom = QSpinBox(); self.zoom.setRange(50,250); self.zoom.setSingleStep(10); self.zoom.setValue(100); self.zoom.setSuffix("%")
        self.zoom.valueChanged.connect(self.render_page)
        self.open_btn = QPushButton("Abrir PDF"); self.open_btn.clicked.connect(self.open_external)
        nav.addWidget(self.info,1); nav.addWidget(self.prev); nav.addWidget(self.next); nav.addWidget(QLabel("Zoom")); nav.addWidget(self.zoom); nav.addWidget(self.open_btn)
        pv.addLayout(nav)
        self.page_view = QLabel("Vista previa del PDF")
        self.page_view.setAlignment(Qt.AlignCenter)
        self.page_view.setMinimumSize(0,0)
        self.page_view.setStyleSheet("background:#E7F0F9;color:#18324B;")
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(False)
        self.page_scroll.setAlignment(Qt.AlignCenter)
        self.page_scroll.setWidget(self.page_view)
        pv.addWidget(self.page_scroll,1)
        split.addWidget(preview); split.setSizes([500,750])
        root.addWidget(split,1)

        bottom = QHBoxLayout()
        self.status = QLabel("Listo. Primero elige una carpeta e indexa tus PDF.")
        self.progress = QProgressBar(); self.progress.setMaximumWidth(260)
        btn_export = QPushButton("Exportar resultados CSV"); btn_export.clicked.connect(self.export_csv)
        btn_backup = QPushButton("Respaldar catálogo"); btn_backup.clicked.connect(self.backup)
        bottom.addWidget(self.status,1); bottom.addWidget(self.progress); bottom.addWidget(btn_export); bottom.addWidget(btn_backup)
        root.addLayout(bottom)

        self.results.itemSelectionChanged.connect(self.selection_changed)

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #F2F6FB; color: #18324B; font-size: 10pt; }
            QMenuBar, QMenu { background-color: #123B63; color: #FFFFFF; }
            QMenuBar::item:selected, QMenu::item:selected { background-color: #2878B8; }
            QPushButton { background-color: #1769AA; color: white; border: 0; border-radius: 5px; padding: 7px 11px; }
            QPushButton:hover { background-color: #0F548C; }
            QPushButton:pressed { background-color: #0A416F; }
            QLineEdit, QComboBox, QSpinBox { background: white; color: #18324B; border: 1px solid #A9C4DF; border-radius: 4px; padding: 5px; }
            QTreeWidget { background: white; alternate-background-color: #EAF3FC; border: 1px solid #B7CDE2; selection-background-color: #B9D9F5; selection-color: #123B63; }
            QHeaderView::section { background: #174B78; color: white; padding: 6px; border: 0; }
            QScrollArea { background: #E7F0F9; border: 1px solid #B7CDE2; }
            QStatusBar { background: #DCEBFA; color: #18324B; }
            QProgressBar { background: white; border: 1px solid #A9C4DF; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background: #2878B8; }
        """)

        self.create_menu()

    def create_menu(self):
        file_menu = self.menuBar().addMenu("Archivo")
        act_folder = QAction("Elegir carpeta",self); act_folder.triggered.connect(self.choose_folder)
        act_index = QAction("Indexar PDF",self); act_index.triggered.connect(self.start_index)
        act_exit = QAction("Salir",self); act_exit.triggered.connect(self.close)
        file_menu.addActions([act_folder,act_index,act_exit])
        help_menu = self.menuBar().addMenu("Ayuda")
        about = QAction("Acerca de",self)
        about.triggered.connect(lambda: QMessageBox.information(self,APP_NAME,
            "Busca texto dentro de PDF digitales y escaneados.\\nLos resultados indican el documento y la página."))
        help_menu.addAction(about)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self,"Selecciona la carpeta de PDF",self.folder.text() or str(Path.home()))
        if folder:
            self.folder.setText(folder)
            self.cfg["folder"] = folder; write_config(self.cfg)

    def start_index(self):
        folder = self.folder.text().strip()
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(self,"Carpeta requerida","Selecciona una carpeta válida."); return
        self.cfg["folder"] = folder; write_config(self.cfg)
        if self.ocr.isChecked() and not locate_tesseract():
            ans = QMessageBox.question(self,"Falta Tesseract",
                "No se detectó Tesseract OCR. ¿Continuar indexando solo PDF con texto digital?\\n"
                "Para PDF escaneados instala Tesseract (consulta LEEME.txt).")
            if ans != QMessageBox.Yes: return
            use_ocr = False
        else: use_ocr = self.ocr.isChecked()
        self.progress.setValue(0)
        self.worker = IndexWorker(folder,use_ocr,self.lang.currentText())
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_msg.connect(self.on_finished)
        self.worker.start()
        self.status.setText("Indexando documentos; puedes esperar a que termine...")

    def on_progress(self,i,total,msg):
        self.progress.setMaximum(total); self.progress.setValue(i); self.status.setText(msg)
    def on_finished(self,msg):
        self.status.setText(msg)
        QMessageBox.information(self,"Indexación",msg)

    def search(self):
        term = self.query.text().strip()
        if not term:
            QMessageBox.information(self,"Buscar","Escribe una palabra o frase."); return
        con = db_connect()
        self.results.clear()
        params=[]; where=[]
        if self.fav_only.isChecked(): where.append("p.favorite=1")
        cat=self.category.currentText()
        if cat!="Todas": where.append("p.category=?"); params.append(cat)
        if self.scope.currentIndex()==1:
            sql="SELECT p.id,p.path,p.name,0,'' FROM pdfs p WHERE p.name LIKE ?"
            params.insert(0,"%"+term+"%")
            if where: sql += " AND " + " AND ".join(where)
            rows=con.execute(sql,params).fetchall()
        else:
            sql="""SELECT p.id,p.path,p.name,t.page_no,t.content FROM page_text t
                   JOIN pdfs p ON p.id=t.pdf_id WHERE t.content LIKE ?"""
            params.insert(0,"%"+term+"%")
            if where: sql += " AND " + " AND ".join(where)
            sql += " ORDER BY p.name,t.page_no"
            rows=con.execute(sql,params).fetchall()
        con.close()
        for pid,path,name,page,content in rows:
            item=QTreeWidgetItem([f"{name}  —  página {page or '-'}", self.snippet(content,term)])
            item.setData(0,Qt.UserRole,(path,page or 1))
            self.results.addTopLevelItem(item)
        self.status.setText(f"{len(rows)} coincidencia(s) encontradas.")
        self.results.expandAll()

    @staticmethod
    def snippet(content,term):
        if not content: return "Coincidencia en el nombre del archivo"
        s=content.replace("\\n"," ").replace("\\r"," ")
        i=s.lower().find(term.lower())
        if i<0: return s[:150]
        return ("…" if i>45 else "") + s[max(0,i-45):i+len(term)+90] + "…"

    def selection_changed(self):
        items=self.results.selectedItems()
        if not items: return
        data=items[0].data(0,Qt.UserRole)
        if data:
            self.current_path,self.current_page=data
            self.render_page()

    def render_page(self):
        if not self.current_path: return
        try:
            doc=fitz.open(self.current_path)
            self.current_page=max(1,min(self.current_page,len(doc)))
            page=doc[self.current_page-1]
            scale=self.zoom.value()/100*1.25
            pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
            image=QImage(pix.samples,pix.width,pix.height,pix.stride,QImage.Format_RGB888).copy()
            pm=QPixmap.fromImage(image)
            self.page_view.setPixmap(pm)
            self.page_view.resize(pm.size())
            self.info.setText(f"{Path(self.current_path).name} — página {self.current_page} de {len(doc)}")
            doc.close()
        except Exception as e:
            self.page_view.setText(f"No se pudo mostrar la página: {e}")

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.current_path: self.render_page()

    def change_page(self,delta):
        if self.current_path:
            self.current_page+=delta; self.render_page()

    def open_result(self,item,column):
        data=item.data(0,Qt.UserRole)
        if data:
            self.current_path,self.current_page=data
            self.render_page()

    def open_external(self):
        if self.current_path and Path(self.current_path).exists():
            os.startfile(self.current_path)

    def context_menu(self,pos):
        item=self.results.itemAt(pos)
        if not item: return
        data=item.data(0,Qt.UserRole)
        if not data: return
        path,page=data
        menu=QMenu(self)
        fav=menu.addAction("Agregar / quitar favorito")
        opena=menu.addAction("Abrir PDF")
        show=menu.addAction("Mostrar en carpeta")
        chosen=menu.exec(self.results.mapToGlobal(pos))
        if chosen==opena: os.startfile(path)
        elif chosen==show: subprocess.Popen(f'explorer /select,"{path}"')
        elif chosen==fav:
            con=db_connect()
            con.execute("UPDATE pdfs SET favorite=1-favorite WHERE path=?",(path,))
            con.commit(); con.close()
            self.search()

    def export_csv(self):
        path,_=QFileDialog.getSaveFileName(self,"Guardar resultados","resultados_pdf.csv","CSV (*.csv)")
        if not path:return
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(["Documento/página","Coincidencia","Ruta"])
            for i in range(self.results.topLevelItemCount()):
                it=self.results.topLevelItem(i); data=it.data(0,Qt.UserRole)
                w.writerow([it.text(0),it.text(1),data[0] if data else ""])
        QMessageBox.information(self,"Exportación","Archivo CSV guardado.")

    def backup(self):
        path,_=QFileDialog.getSaveFileName(self,"Guardar respaldo","catalogo_respaldo.sqlite3","SQLite (*.sqlite3)")
        if path:
            try: shutil.copy2(DB_PATH,path); QMessageBox.information(self,"Respaldo","Catálogo respaldado.")
            except Exception as e: QMessageBox.critical(self,"Error",str(e))

def main():
    app=QApplication(sys.argv)
    app.setStyle("Fusion")
    win=MainWindow(); win.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
