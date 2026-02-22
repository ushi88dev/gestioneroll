import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
import csv
from tkcalendar import DateEntry
#import winsound  # solo Windows
import sys
import time

# Connessione database
conn = sqlite3.connect('supporti.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS movimenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT,
    articolo TEXT,
    direzione TEXT,
    magazzino TEXT,
    quantita INTEGER
)
''')
conn.commit()

# ────────────────────────────────────────────────
# FUNZIONI DI LOGICA
# ────────────────────────────────────────────────

def calcola_saldo(articolo=None, magazzino=None):
    query = 'SELECT SUM(CASE WHEN direzione = "ENTRATA" THEN quantita ELSE -quantita END) FROM movimenti'
    params = []
    conditions = []
    if articolo:
        conditions.append('articolo = ?')
        params.append(articolo)
    if magazzino:
        conditions.append('magazzino = ?')
        params.append(magazzino)
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    cursor.execute(query, params)
    result = cursor.fetchone()[0]
    return result if result is not None else 0

def registra_movimenti():
    data_str = calendario.get_date().strftime('%Y-%m-%d')
    magazzino = magazzino_var.get()

    if not magazzino:
        messagebox.showerror("Errore", "Seleziona il magazzino!")
        return

    # Direzione forzata per Carne e Ortofrutta
    if magazzino in ["Carne", "Ortofrutta"]:
        direzione = "ENTRATA"
    else:
        direzione = direzione_var.get()

    try:
        q_roll    = int(roll_entry.get()    or 0)
        q_griglia = int(griglia_entry.get() or 0)
        q_cpr     = int(cpr_entry.get()     or 0)
    except ValueError:
        messagebox.showerror("Errore", "Le quantità devono essere numeri interi!")
        return

    if q_roll == 0 and q_griglia == 0 and q_cpr == 0:
        messagebox.showerror("Errore", "Inserisci almeno una quantità maggiore di zero!")
        return

    articoli_qty = [("Roll", q_roll), ("Griglia", q_griglia), ("Cassetta CPR", q_cpr)]

    for articolo, qty in articoli_qty:
        if qty > 0:
            cursor.execute(
                'INSERT INTO movimenti (data, articolo, direzione, magazzino, quantita) VALUES (?, ?, ?, ?, ?)',
                (data_str, articolo, direzione, magazzino, qty)
            )

    conn.commit()

    # Pulizia campi
    roll_entry.delete(0, tk.END)
    griglia_entry.delete(0, tk.END)
    cpr_entry.delete(0, tk.END)

    # Beep conferma
    #winsound.Beep(800, 120)
    beep_semplice()
    time.sleep(0.3)
    beep_semplice()

    aggiorna_inventario()
    aggiorna_storico()

def annulla_ultimo():
    if not messagebox.askyesno("Conferma", "Annullare l'ultimo movimento inserito?"):
        return

    cursor.execute('DELETE FROM movimenti WHERE id = (SELECT MAX(id) FROM movimenti)')
    conn.commit()

    #winsound.Beep(400, 200)  # beep diverso per annullamento
    beep_semplice()
    time.sleep(0.3)
    beep_semplice()
    aggiorna_inventario()
    aggiorna_storico()

def aggiorna_direzione(*args):
    mag = magazzino_var.get()
    if mag in ["Carne", "Ortofrutta"]:
        direzione_var.set("ENTRATA")
        rb_entrata.config(state="disabled")
        rb_uscita.config(state="disabled")
    else:
        rb_entrata.config(state="normal")
        rb_uscita.config(state="normal")
        if direzione_var.get() not in ["ENTRATA", "USCITA"]:
            direzione_var.set("ENTRATA")

def aggiorna_inventario():
    for row in tree_inventario.get_children():
        tree_inventario.delete(row)

    articoli = ['Roll', 'Griglia', 'Cassetta CPR']
    magazzini = ['Carne', 'Ortofrutta', 'Freschi', 'Secchi']

    # Dettaglio per magazzino × articolo
    for mag in magazzini:
        for art in articoli:
            saldo = calcola_saldo(art, mag)
            tree_inventario.insert('', 'end', values=(mag, art, saldo))

    # Totali per magazzino
    tree_inventario.insert('', 'end', values=('', '', ''))
    for mag in magazzini:
        saldo = calcola_saldo(magazzino=mag)
        tree_inventario.insert('', 'end', values=(f"Totale {mag}", '', saldo), tags=('total',))

    # Totali per articolo
    tree_inventario.insert('', 'end', values=('', '', ''))
    for art in articoli:
        saldo = calcola_saldo(articolo=art)
        tree_inventario.insert('', 'end', values=('', f"Totale {art}", saldo), tags=('total',))

def aggiorna_storico():
    for row in tree_storico.get_children():
        tree_storico.delete(row)

    cursor.execute('SELECT data, articolo, direzione, magazzino, quantita FROM movimenti ORDER BY id DESC LIMIT 150')
    for row in cursor.fetchall():
        tree_storico.insert('', 'end', values=row)

def genera_report():
    data_rep = calendario_report.get_date().strftime('%Y-%m-%d')
    for row in tree_report.get_children():
        tree_report.delete(row)

    articoli = ['Roll', 'Griglia', 'Cassetta CPR']
    magazzini = ['Carne', 'Ortofrutta', 'Freschi', 'Secchi']

    for mag in magazzini:
        for art in articoli:
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN direzione = 'ENTRATA' THEN quantita ELSE 0 END) as entrate,
                    SUM(CASE WHEN direzione = 'USCITA'  THEN quantita ELSE 0 END) as uscite
                FROM movimenti 
                WHERE data = ? AND articolo = ? AND magazzino = ?
            ''', (data_rep, art, mag))
            entrate, uscite = cursor.fetchone()
            entrate = entrate or 0
            uscite  = uscite  or 0
            tree_report.insert('', 'end', values=(data_rep, mag, art, entrate, uscite))

def esporta_csv():
    with open('movimenti_supporti.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Data', 'Articolo', 'Direzione', 'Magazzino', 'Quantità'])
        cursor.execute('SELECT data, articolo, direzione, magazzino, quantita FROM movimenti ORDER BY id')
        writer.writerows(cursor.fetchall())
    messagebox.showinfo("Esportato", "Creato file: movimenti_supporti.csv")

def beep_semplice():
    sys.stdout.write('\a')
    sys.stdout.flush()
# ────────────────────────────────────────────────
# INTERFACCIA GRAFICA
# ────────────────────────────────────────────────

root = tk.Tk()
root.title("Gestione Roll / Griglie / CPR")
root.geometry("800x400")
root.resizable(False, False)

notebook = ttk.Notebook(root)
notebook.pack(pady=8, padx=8, fill="both", expand=True)

# ── Tab Registrazione ───────────────────────────
frame_reg = tk.Frame(notebook)
notebook.add(frame_reg, text="Registrazione")

frame = tk.LabelFrame(frame_reg, text=" Nuovo movimento ", padx=12, pady=12)
frame.pack(padx=10, pady=10, fill="x")

tk.Label(frame, text="Data:", font=("Arial", 10)).grid(row=0, column=0, sticky="e", pady=6, padx=(0,10))
calendario = DateEntry(frame, width=13, background='darkblue', foreground='white', borderwidth=2,
                       date_pattern='yyyy-mm-dd', font=("Arial", 10))
calendario.grid(row=0, column=1, sticky="w", pady=6)
calendario.set_date(date.today())

tk.Label(frame, text="Magazzino:", font=("Arial", 10)).grid(row=1, column=0, sticky="e", pady=6, padx=(0,10))
magazzino_var = tk.StringVar()
magazzino_combo = ttk.Combobox(frame, textvariable=magazzino_var,
                                values=['Carne', 'Ortofrutta', 'Freschi', 'Secchi'],
                                state="readonly", width=25, font=("Arial", 10))
magazzino_combo.grid(row=1, column=1, sticky="w", pady=6)
magazzino_var.trace_add("write", aggiorna_direzione)

tk.Label(frame, text="Movimento:", font=("Arial", 10)).grid(row=2, column=0, sticky="ne", pady=6, padx=(0,10))

direzione_frame = tk.Frame(frame)
direzione_frame.grid(row=2, column=1, sticky="w", pady=6)

direzione_var = tk.StringVar(value="ENTRATA")
rb_entrata = tk.Radiobutton(direzione_frame, text="ENTRATA", variable=direzione_var, value="ENTRATA", font=("Arial", 10))
rb_entrata.pack(side="left", padx=(0,20))
rb_uscita  = tk.Radiobutton(direzione_frame, text="USCITA",  variable=direzione_var, value="USCITA",  font=("Arial", 10))
rb_uscita.pack(side="left")

# Quantità

lbl_font = ("Arial", 11, "bold")
entry_font = ("Arial", 12)
"""
tk.Label(frame, text="Roll:",font=lbl_font).grid(row=3, column=0, sticky="e", pady=3, padx=(0,2))
roll_entry = tk.Entry(frame, width=6, font=("Arial", 11), justify="center")
roll_entry.grid(row=3, column=1, sticky="w", pady=3, padx=(2,6))

tk.Label(frame, text="Griglia:",  font=lbl_font).grid(row=3, column=2, sticky="e", pady=3, padx=(6,2))
griglia_entry = tk.Entry(frame, width=6, font=("Arial", 11), justify="center")
griglia_entry.grid(row=3, column=3, sticky="w", pady=3, padx=(2,6))

tk.Label(frame, text="Cassetta CPR:", font=lbl_font).grid(row=3, column=4, sticky="e", pady=3, padx=(6,2))
cpr_entry = tk.Entry(frame, width=6, font=("Arial", 11), justify="center")
cpr_entry.grid(row=3, column=5, sticky="w", pady=3, padx=0)
"""
# Frame Roll
frame_roll = tk.Frame(frame)
frame_roll.grid(row=3, column=0, sticky="w", padx=(0, 6), pady=4)
tk.Label(frame_roll, text="Roll:", font=lbl_font).pack(side="left", padx=(0, 4))
roll_entry = tk.Entry(frame_roll, width=7, font=entry_font, justify="center")
roll_entry.pack(side="left")

# Frame Griglia
frame_griglia = tk.Frame(frame)
frame_griglia.grid(row=3, column=1, sticky="w", padx=(0,6), pady=4)
tk.Label(frame_griglia, text="Griglia:", font=lbl_font).pack(side="left", padx=(0, 4))
griglia_entry = tk.Entry(frame_griglia, width=7, font=entry_font, justify="center")
griglia_entry.pack(side="left")

# Frame Cassetta CPR
frame_cpr = tk.Frame(frame)
frame_cpr.grid(row=3, column=2, sticky="w", padx=(0,6), pady=4)
tk.Label(frame_cpr, text="Cassetta CPR:", font=lbl_font).pack(side="left", padx=(0, 4))
cpr_entry = tk.Entry(frame_cpr, width=7, font=entry_font, justify="center")
cpr_entry.pack(side="left")

# Pulsanti
btn_frame = tk.Frame(frame)
btn_frame.grid(row=6, column=0, columnspan=2, pady=18)

tk.Button(btn_frame, text="REGISTRA", command=registra_movimenti,
          bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=16, height=2).pack(side="left", padx=20)

tk.Button(btn_frame, text="ANNULLA ULTIMO", command=annulla_ultimo,
          bg="#F44336", fg="white", font=("Arial", 10, "bold"), width=16).pack(side="left", padx=20)

# ── Tab Inventario ──────────────────────────────
frame_inv = tk.Frame(notebook)
notebook.add(frame_inv, text="Inventario")

tk.Label(frame_inv, text="Inventario attuale", font=("Arial", 11, "bold")).pack(pady=8)
tree_inventario = ttk.Treeview(frame_inv, columns=('Magazzino','Articolo','Saldo'), show='headings', height=18)
tree_inventario.heading('Magazzino', text='Magazzino')
tree_inventario.heading('Articolo', text='Articolo')
tree_inventario.heading('Saldo', text='Saldo')
tree_inventario.column('Magazzino', width=180)
tree_inventario.column('Articolo', width=180)
tree_inventario.column('Saldo', width=100, anchor='center')
tree_inventario.tag_configure('total', font=('Arial', 10, 'bold'))
tree_inventario.pack(padx=10, pady=5, fill="both", expand=True)

# ── Tab Storico ─────────────────────────────────
frame_sto = tk.Frame(notebook)
notebook.add(frame_sto, text="Storico")

tk.Label(frame_sto, text="Ultimi movimenti", font=("Arial", 11, "bold")).pack(pady=8)
tree_storico = ttk.Treeview(frame_sto, columns=('Data','Articolo','Direzione','Magazzino','Qtà'), show='headings', height=18)
tree_storico.heading('Data', text='Data')
tree_storico.heading('Articolo', text='Articolo')
tree_storico.heading('Direzione', text='Mov.')
tree_storico.heading('Magazzino', text='Magazzino')
tree_storico.heading('Qtà', text='Qtà')
tree_storico.column('Data', width=90)
tree_storico.column('Articolo', width=140)
tree_storico.column('Direzione', width=70)
tree_storico.column('Magazzino', width=140)
tree_storico.column('Qtà', width=60, anchor='center')
tree_storico.pack(padx=10, pady=5, fill="both", expand=True)

# ── Tab Report ──────────────────────────────────
frame_rep = tk.Frame(notebook)
notebook.add(frame_rep, text="Report giorno")

frame_rep_top = tk.Frame(frame_rep)
frame_rep_top.pack(pady=8)

tk.Label(frame_rep_top, text="Data:", font=("Arial", 10)).pack(side="left", padx=5)
calendario_report = DateEntry(frame_rep_top, width=13, background='darkblue', foreground='white', borderwidth=2,
                              date_pattern='yyyy-mm-dd', font=("Arial", 10))
calendario_report.pack(side="left", padx=5)
calendario_report.set_date(date.today())

tk.Button(frame_rep_top, text="Genera", command=genera_report,
          bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(side="left", padx=10)

tree_report = ttk.Treeview(frame_rep, columns=('Data','Magazzino','Articolo','Entrate','Uscite'), show='headings', height=18)
tree_report.heading('Data', text='Data')
tree_report.heading('Magazzino', text='Magazzino')
tree_report.heading('Articolo', text='Articolo')
tree_report.heading('Entrate', text='Entrate')
tree_report.heading('Uscite', text='Uscite')
tree_report.column('Data', width=90)
tree_report.column('Magazzino', width=140)
tree_report.column('Articolo', width=140)
tree_report.column('Entrate', width=90, anchor='center')
tree_report.column('Uscite', width=90, anchor='center')
tree_report.pack(padx=10, pady=5, fill="both", expand=True)

# Esporta globale
tk.Button(root, text="Esporta tutto in CSV", command=esporta_csv,
          bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(pady=8)

# Avvio
aggiorna_inventario()
aggiorna_storico()
genera_report()
aggiorna_direzione()  # stato iniziale

root.mainloop()
conn.close()
