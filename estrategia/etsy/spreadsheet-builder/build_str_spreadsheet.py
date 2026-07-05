"""
STR / Vacation Rental Financial System Builder
================================================
Crea el Google Sheets completo para el Producto #1 de Etsy:
8 pestanas, formulas, dropdowns, formato ejecutivo y datos de ejemplo.

Requisitos:
    pip install google-auth google-api-python-client

Uso:
    export GOOGLE_APPLICATION_CREDENTIALS="/ruta/a/key.json"
    python build_str_spreadsheet.py --id 1QDLhbEGhoPUmD4jKy57GTWb8E3RwJ2UwFomrbCmvbhA
"""
import argparse, os, time
from googleapiclient.discovery import build
from google.oauth2 import service_account

# ─── PALETA ───────────────────────────────────────────────────────────────────
C_DARK  = {"red":0.118,"green":0.122,"blue":0.157}
C_ACNT  = {"red":0.204,"green":0.596,"blue":0.859}
C_GRN   = {"red":0.180,"green":0.800,"blue":0.443}
C_AMB   = {"red":0.945,"green":0.769,"blue":0.059}
C_RED   = {"red":0.906,"green":0.298,"blue":0.235}
C_WHITE = {"red":1.0,  "green":1.0,  "blue":1.0  }
C_LGRAY = {"red":0.957,"green":0.961,"blue":0.969}
C_MGRAY = {"red":0.741,"green":0.765,"blue":0.800}
C_TEXT  = {"red":0.153,"green":0.169,"blue":0.212}

SCOPES     = ["https://www.googleapis.com/auth/spreadsheets"]
PLATFORMS  = ["Airbnb","Vrbo","Booking.com","Direct","Other"]
PROPS      = ["Property 1","Property 2","Property 3","Property 4","Property 5"]
PROPS_ALL  = PROPS + ["ALL"]
STATUS     = ["Confirmed","Pending","Cancelled","Completed"]
EXP_CAT    = [
    "Advertising (Sch E L19)","Auto & Travel (Sch E L6)",
    "Cleaning & Maint. (Sch E L14)","Commissions (Sch E L5)",
    "Insurance (Sch E L9)","Legal & Professional (Sch E L10)",
    "Management Fees (Sch E L11)","Mortgage Interest (Sch E L12)",
    "Other Interest (Sch E L13)","Repairs (Sch E L14)",
    "Supplies (Sch E L15)","Taxes (Sch E L16)",
    "Utilities (Sch E L17)","Other Expenses (Sch E L19)",
]
SID = {"setup":100,"bookings":101,"expenses":102,"dashboard":103,
       "pl":104,"tax":105,"cleaning":106,"supplies":107}

# ─── HELPERS FORMATO ──────────────────────────────────────────────────────────
def rgb(c): return {"red":c["red"],"green":c["green"],"blue":c["blue"]}

def fmt(bg=None,bold=False,sz=10,fg=None,ha="LEFT",nf=None,wrap=False):
    f = {"textFormat":{"bold":bold,"fontSize":sz,
                       "foregroundColor":rgb(fg) if fg else rgb(C_TEXT),
                       "fontFamily":"Inter"},
         "horizontalAlignment":ha,"verticalAlignment":"MIDDLE",
         "wrapStrategy":"WRAP" if wrap else "OVERFLOW_CELL"}
    if bg: f["backgroundColor"]=rgb(bg)
    if nf: f["numberFormat"]=nf
    return f

def hdr(sz=11): return fmt(bg=C_DARK,bold=True,sz=sz,fg=C_WHITE,ha="CENTER")
def sub():      return fmt(bg=C_LGRAY,bold=True,sz=9,fg=C_TEXT,ha="CENTER")
def alt(i):     return fmt(bg=C_LGRAY if i%2==0 else C_WHITE)
def cur():      return {"type":"NUMBER","pattern":"$#,##0.00"}
def pct():      return {"type":"NUMBER","pattern":"0.0%"}

# ─── HELPERS REQUESTS ─────────────────────────────────────────────────────────
def row(vals, f=None):
    cells = []
    for v in vals:
        c={}
        if v is not None and v!="":
            if str(v).startswith("="): c["userEnteredValue"]={"formulaValue":v}
            elif isinstance(v,(int,float)): c["userEnteredValue"]={"numberValue":float(v)}
            else: c["userEnteredValue"]={"stringValue":str(v)}
        if f: c["userEnteredFormat"]=f
        cells.append(c)
    return {"values":cells}

def uc(sid,r,c,rows):
    return {"updateCells":{"start":{"sheetId":sid,"rowIndex":r,"columnIndex":c},
                           "rows":rows,"fields":"userEnteredValue,userEnteredFormat"}}
def cw(sid,c1,c2,w):
    return {"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"COLUMNS",
            "startIndex":c1,"endIndex":c2},"properties":{"pixelSize":w},"fields":"pixelSize"}}
def rh(sid,r1,r2,h):
    return {"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"ROWS",
            "startIndex":r1,"endIndex":r2},"properties":{"pixelSize":h},"fields":"pixelSize"}}
def freeze(sid,rows=1,cols=0):
    return {"updateSheetProperties":{"properties":{"sheetId":sid,"gridProperties":{
            "frozenRowCount":rows,"frozenColumnCount":cols}},
            "fields":"gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}}
def merge(sid,r1,c1,r2,c2):
    return {"mergeCells":{"range":{"sheetId":sid,"startRowIndex":r1,"endRowIndex":r2,
            "startColumnIndex":c1,"endColumnIndex":c2},"mergeType":"MERGE_ALL"}}
def tabcolor(sid,c):
    return {"updateSheetProperties":{"properties":{"sheetId":sid,
            "tabColorStyle":{"rgbColor":rgb(c)}},"fields":"tabColorStyle"}}
def addsheet(title,sid,color=None):
    props={"title":title,"sheetId":sid,"gridProperties":{"rowCount":200,"columnCount":20}}
    if color: props["tabColorStyle"]={"rgbColor":rgb(color)}
    return {"addSheet":{"properties":props}}
def delsheet(sid): return {"deleteSheet":{"sheetId":sid}}
def dropdown(sid,r1,r2,c1,c2,opts):
    return {"setDataValidation":{"range":{"sheetId":sid,"startRowIndex":r1,"endRowIndex":r2,
            "startColumnIndex":c1,"endColumnIndex":c2},
            "rule":{"condition":{"type":"ONE_OF_LIST",
                    "values":[{"userEnteredValue":o} for o in opts]},
                    "showCustomUi":True,"strict":True}}}

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: SETUP
# ══════════════════════════════════════════════════════════════════════════════
def tab_setup(sid):
    q=[]
    q.append(merge(sid,0,0,2,6))
    q.append(uc(sid,0,0,[
        row(["🏡  STR Financial System — Setup & Configuration"]+[""]*5,
            fmt(bg=C_DARK,bold=True,sz=16,fg=C_WHITE,ha="CENTER")),
        row(["v1.0  |  Multi-Property + Schedule E Ready  |  ⚠️ NOT tax advice"]+[""]*5,
            fmt(bg=C_DARK,sz=9,fg=C_MGRAY,ha="CENTER")),
    ]))
    q.append(merge(sid,3,0,4,6))
    q.append(uc(sid,3,0,[row(["STEP 1 — Your Properties"]+[""]*5,hdr(11))]))
    q.append(uc(sid,4,0,[row(
        ["Property #","Property Name","Address","Platform(s)","Nightly Rate ($)","Notes"],sub())]))
    sp=[("Property 1","Beachside Studio","Miami, FL","Airbnb, Vrbo",185,""),
        ("Property 2","Mountain Cabin","Asheville, NC","Airbnb",220,""),
        ("Property 3","","","","",""),("Property 4","","","","",""),
        ("Property 5","","","","","")]
    for i,p in enumerate(sp): q.append(uc(sid,5+i,0,[row(list(p),alt(i))]))
    q.append(merge(sid,11,0,12,6))
    q.append(uc(sid,11,0,[row(["STEP 2 — Platform Commission Rates"]+[""]*5,hdr(11))]))
    q.append(uc(sid,12,0,[row(["Platform","Commission %","Notes","","",""],sub())]))
    fees=[("Airbnb","0.03","3% standard host fee"),("Vrbo","0.05","5% commission"),
          ("Booking.com","0.15","15% commission"),("Direct","0.00","No commission — keep 100%")]
    for i,(p,r_,n) in enumerate(fees):
        q.append(uc(sid,13+i,0,[row([p,r_,n,"","",""],alt(i))]))
    q.append(merge(sid,19,0,20,6))
    q.append(uc(sid,19,0,[row(["STEP 3 — Quick Start Guide"]+[""]*5,hdr(11))]))
    steps=["1. Fill in your property names (up to 5 properties).",
           "2. Adjust commission % if your platform rates differ.",
           "3. → BOOKINGS: log each reservation as confirmed.",
           "4. → EXPENSES: log every expense with its Schedule E category.",
           "5. → DASHBOARD: review ADR, Occupancy %, and RevPAR weekly.",
           "6. → TAX SUMMARY: hand this tab to your CPA at tax time.",
           "⚠️  DISCLAIMER: Organizational tool only. NOT tax/legal/financial advice. Consult a licensed CPA before filing."]
    q.append(uc(sid,20,0,[row([s]+[""]*5,fmt(bg=C_LGRAY,wrap=True,sz=9)) for s in steps]))
    for i,w in enumerate([80,160,200,160,120,200]): q.append(cw(sid,i,i+1,w))
    q+=[rh(sid,0,2,38),freeze(sid,1,0),tabcolor(sid,C_ACNT)]
    return q

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: BOOKINGS
# ══════════════════════════════════════════════════════════════════════════════
def tab_bookings(sid):
    q=[]
    q.append(merge(sid,0,0,1,12))
    q.append(uc(sid,0,0,[row(["📅  BOOKINGS — Income Log"]+[""]*11,hdr(11))]))
    q.append(uc(sid,1,0,[row(
        ["Check-In","Check-Out","Nights","Property","Platform","Guest",
         "Gross ($)","Platform Fee ($)","Cleaning Fee ($)","Payout Net ($)","Status","Notes"],sub())]))
    samp=[
        ["2026-07-01","2026-07-05","=C3-B3","Property 1","Airbnb","John D.",
         350,"=G3*VLOOKUP(E3,Setup!A14:B17,2,0)",50,"=G3-H3-I3","Completed",""],
        ["2026-07-10","2026-07-14","=C4-B4","Property 2","Vrbo","Sarah M.",
         420,"=G4*VLOOKUP(E4,Setup!A14:B17,2,0)",60,"=G4-H4-I4","Confirmed",""],
        ["2026-08-01","2026-08-04","=C5-B5","Property 1","Direct","Mike R.",
         280,"=G5*VLOOKUP(E5,Setup!A14:B17,2,0)",50,"=G5-H5-I5","Confirmed",""],
    ]
    for i,r_ in enumerate(samp): q.append(uc(sid,2+i,0,[row(r_,alt(i))]))
    for i in range(47):
        q.append(uc(sid,2+len(samp)+i,0,[row([""]*12,alt(i+len(samp)))]))
    q.append(dropdown(sid,2,100,3,4,PROPS))
    q.append(dropdown(sid,2,100,4,5,PLATFORMS))
    q.append(dropdown(sid,2,100,10,11,STATUS))
    for i,w in enumerate([90,90,55,120,100,140,90,110,100,100,100,160]):
        q.append(cw(sid,i,i+1,w))
    q+=[freeze(sid,2,0),tabcolor(sid,C_GRN)]
    return q

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: EXPENSES
# ══════════════════════════════════════════════════════════════════════════════
def tab_expenses(sid):
    q=[]
    q.append(merge(sid,0,0,1,9))
    q.append(uc(sid,0,0,[row(
        ["💳  EXPENSES — Organized by Schedule E Category"]+[""]*8,hdr(11))]))
    q.append(uc(sid,1,0,[row(
        ["Date","Property","Category (Sch E)","Vendor","Amount ($)",
         "Payment Method","Receipt?","Deductible?","Notes"],sub())]))
    samp=[
        ["2026-07-02","Property 1","Cleaning & Maint. (Sch E L14)","CleanPro LLC",
         120,"Bank Transfer","Yes","Yes","Post-checkout cleaning"],
        ["2026-07-05","Property 1","Supplies (Sch E L15)","Amazon",
         45.5,"Credit Card","Yes","Yes","Coffee, toiletries restock"],
        ["2026-07-10","Property 2","Utilities (Sch E L17)","City Water",
         85,"Auto-pay","No","Yes","Monthly water bill"],
        ["2026-07-15","ALL","Insurance (Sch E L9)","State Farm",
         180,"Bank Transfer","Yes","Yes","Monthly STR insurance"],
        ["2026-07-20","Property 2","Repairs (Sch E L14)","Handyman Mike",
         250,"Cash","Yes","Yes","Faucet repair"],
    ]
    for i,r_ in enumerate(samp): q.append(uc(sid,2+i,0,[row(r_,alt(i))]))
    for i in range(45):
        q.append(uc(sid,2+len(samp)+i,0,[row([""]*9,alt(i+len(samp)))]))
    q.append(dropdown(sid,2,100,1,2,PROPS_ALL))
    q.append(dropdown(sid,2,100,2,3,EXP_CAT))
    q.append(dropdown(sid,2,100,6,7,["Yes","No"]))
    q.append(dropdown(sid,2,100,7,8,["Yes","No","Partial"]))
    for i,w in enumerate([90,110,270,150,90,130,80,90,200]):
        q.append(cw(sid,i,i+1,w))
    q+=[freeze(sid,2,0),tabcolor(sid,C_AMB)]
    return q

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def tab_dashboard(sid):
    q=[]
    q.append(merge(sid,0,0,2,8))
    q.append(uc(sid,0,0,[
        row(["📊  DASHBOARD — Portfolio Performance"]+[""]*7,
            fmt(bg=C_DARK,bold=True,sz=16,fg=C_WHITE,ha="CENTER")),
        row(["Auto-calculated from Bookings & Expenses | Update data to refresh"]+[""]*7,
            fmt(bg=C_DARK,sz=9,fg=C_MGRAY,ha="CENTER")),
    ]))
    # KPI summary cards
    q.append(merge(sid,3,0,4,8))
    q.append(uc(sid,3,0,[row(["KEY METRICS — All Properties Combined"]+[""]*7,hdr(11))]))
    kpis=[("Total Payout","=SUM(Bookings!J3:J100)"),
          ("Total Expenses","=SUM(Expenses!E3:E100)"),
          ("Net Profit","=D5-D6"),
          ("Profit Margin","=IFERROR(D7/D5,0)")]
    for i,(lbl,fml) in enumerate(kpis):
        col=i*2
        q.append(merge(sid,4,col,5,col+2))
        q.append(merge(sid,5,col,6,col+2))
        q.append(uc(sid,4,col,[row([fml],fmt(bg=C_DARK,bold=True,sz=22,fg=C_ACNT,ha="CENTER",
                                            nf=pct() if "Margin" in lbl else cur()))]))
        q.append(uc(sid,5,col,[row([lbl],fmt(bg=C_DARK,sz=9,fg=C_MGRAY,ha="CENTER"))]))
    # Per-property table
    q.append(merge(sid,8,0,9,8))
    q.append(uc(sid,8,0,[row(["PERFORMANCE BY PROPERTY"]+[""]*7,hdr(11))]))
    q.append(uc(sid,9,0,[row(
        ["Property","# Bookings","Nights Booked","ADR ($)","Occupancy %",
         "RevPAR ($)","Net Revenue ($)","Expenses ($)"],sub())]))
    for i,p in enumerate(PROPS):
        r_=10+i
        vals=[p,
              f'=COUNTIF(Bookings!D3:D100,"{p}")',
              f'=SUMIF(Bookings!D3:D100,"{p}",Bookings!C3:C100)',
              f'=IFERROR(SUMIF(Bookings!D3:D100,"{p}",Bookings!G3:G100)/C{r_+1},0)',
              f'=IFERROR(C{r_+1}/90,0)',
              f'=D{r_+1}*E{r_+1}',
              f'=SUMIF(Bookings!D3:D100,"{p}",Bookings!J3:J100)',
              f'=SUMIF(Expenses!B3:B100,"{p}",Expenses!E3:E100)']
        q.append(uc(sid,r_,0,[row(vals,alt(i))]))
    q.append(uc(sid,15,0,[row(
        ["ALL PROPERTIES","=SUM(B10:B14)","=SUM(C10:C14)",
         "=IFERROR(SUM(D10:D14)/5,0)","=IFERROR(SUM(E10:E14)/5,0)",
         "=IFERROR(SUM(F10:F14)/5,0)","=SUM(G10:G14)","=SUM(H10:H14)"],
        fmt(bg=C_DARK,bold=True,fg=C_WHITE))]))
    for i,w in enumerate([130,90,100,90,90,90,110,100]):
        q.append(cw(sid,i,i+1,w))
    q+=[rh(sid,4,6,50),freeze(sid,2,0),tabcolor(sid,C_ACNT)]
    return q

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: P&L
# ══════════════════════════════════════════════════════════════════════════════
def tab_pl(sid):
    q=[]
    q.append(merge(sid,0,0,2,7))
    q.append(uc(sid,0,0,[
        row(["📈  PROFIT & LOSS — By Property"]+[""]*6,
            fmt(bg=C_DARK,bold=True,sz=14,fg=C_WHITE,ha="CENTER")),
        row(["Auto-calculated. Add bookings & expenses to see results."]+[""]*6,
            fmt(bg=C_DARK,sz=9,fg=C_MGRAY,ha="CENTER")),
    ]))
    cols=["Line Item"]+PROPS+["ALL PROPERTIES"]
    q.append(uc(sid,3,0,[row(cols,sub())]))
    pcols=["B","C","D","E","F"]
    lines=[
        ("── REVENUE ──",True,None),
        ("Gross Bookings",False,'SUMIF(Bookings!D$3:D$100,"{p}",Bookings!G$3:G$100)'),
        ("(-) Platform Fees",False,'SUMIF(Bookings!D$3:D$100,"{p}",Bookings!H$3:H$100)'),
        ("(-) Cleaning Fees",False,'SUMIF(Bookings!D$3:D$100,"{p}",Bookings!I$3:I$100)'),
        ("Net Revenue",False,"{c}5-{c}6-{c}7"),("",False,None),
        ("── EXPENSES ──",True,None),
        ("Cleaning & Maint.",False,'SUMPRODUCT((Expenses!B$3:B$100="{p}")*(ISNUMBER(SEARCH("Cleaning",Expenses!C$3:C$100)))*Expenses!E$3:E$100)'),
        ("Supplies",False,'SUMPRODUCT((Expenses!B$3:B$100="{p}")*(ISNUMBER(SEARCH("Supplies",Expenses!C$3:C$100)))*Expenses!E$3:E$100)'),
        ("Utilities",False,'SUMPRODUCT((Expenses!B$3:B$100="{p}")*(ISNUMBER(SEARCH("Utilities",Expenses!C$3:C$100)))*Expenses!E$3:E$100)'),
        ("Insurance",False,'SUMPRODUCT((Expenses!B$3:B$100="{p}")*(ISNUMBER(SEARCH("Insurance",Expenses!C$3:C$100)))*Expenses!E$3:E$100)'),
        ("Repairs",False,'SUMPRODUCT((Expenses!B$3:B$100="{p}")*(ISNUMBER(SEARCH("Repairs",Expenses!C$3:C$100)))*Expenses!E$3:E$100)'),
        ("Total Expenses",False,"SUM({c}10:{c}14)"),("",False,None),
        ("NET PROFIT",False,"{c}8-{c}15"),
        ("Profit Margin %",False,"IFERROR({c}16/{c}5,0)"),
    ]
    for i,(lbl,is_hdr,fml_tpl) in enumerate(lines):
        r_=4+i
        if is_hdr:
            bg,fg,bold=C_DARK,C_WHITE,True
        else:
            bg=C_LGRAY if i%2==0 else C_WHITE; fg=C_TEXT
            bold=lbl in ("Net Revenue","Total Expenses","NET PROFIT")
        cells=[lbl]
        for j,(p,c) in enumerate(zip(PROPS,pcols)):
            if fml_tpl and not is_hdr:
                fml=fml_tpl.replace("{p}",p).replace("{c}",c)
                cells.append(("=" if not fml.startswith("=") else "")+fml)
            else: cells.append("")
        cells.append(f"=SUM(B{r_+1}:F{r_+1})" if fml_tpl and not is_hdr else "")
        q.append(uc(sid,r_,0,[row(cells,fmt(bg=bg,bold=bold,fg=fg))]))
    for i,w in enumerate([180,110,110,110,110,110,120]):
        q.append(cw(sid,i,i+1,w))
    q+=[freeze(sid,4,1),tabcolor(sid,C_GRN)]
    return q

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6: TAX SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
def tab_tax(sid):
    q=[]
    q.append(merge(sid,0,0,2,5))
    q.append(uc(sid,0,0,[
        row(["🧾  TAX SUMMARY — Schedule E Reference"]+[""]*4,
            fmt(bg=C_DARK,bold=True,sz=14,fg=C_WHITE,ha="CENTER")),
        row(["⚠️  Share with your CPA. For organizational purposes only — NOT tax advice."]+[""]*4,
            fmt(bg=C_AMB,sz=9,fg=C_TEXT,ha="CENTER",bold=True)),
    ]))
    q.append(uc(sid,3,0,[row(
        ["Schedule E Line","Description","Total Expenses ($)","Tax Year","Notes"],sub())]))
    sch_e=[
        ("L5","Commissions",'=SUMPRODUCT((ISNUMBER(SEARCH("Commission",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L6","Auto & Travel",'=SUMPRODUCT((ISNUMBER(SEARCH("Auto",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L9","Insurance",'=SUMPRODUCT((ISNUMBER(SEARCH("Insurance",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L10","Legal & Professional",'=SUMPRODUCT((ISNUMBER(SEARCH("Legal",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L11","Management Fees",'=SUMPRODUCT((ISNUMBER(SEARCH("Management",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L12","Mortgage Interest",'=SUMPRODUCT((ISNUMBER(SEARCH("Mortgage",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L13","Other Interest",'=SUMPRODUCT((ISNUMBER(SEARCH("Other Interest",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L14","Repairs & Maintenance",'=SUMPRODUCT((ISNUMBER(SEARCH("Cleaning",Expenses!C3:C100))+ISNUMBER(SEARCH("Repair",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L15","Supplies",'=SUMPRODUCT((ISNUMBER(SEARCH("Supplies",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L16","Taxes",'=SUMPRODUCT((ISNUMBER(SEARCH("Taxes",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L17","Utilities",'=SUMPRODUCT((ISNUMBER(SEARCH("Utilities",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("L19","Advertising & Other",'=SUMPRODUCT((ISNUMBER(SEARCH("Advertising",Expenses!C3:C100))+ISNUMBER(SEARCH("Other",Expenses!C3:C100)))*Expenses!E3:E100)'),
        ("TOTAL","All Deductible Expenses","=SUM(C5:C16)"),
    ]
    for i,(ln,desc,fml) in enumerate(sch_e):
        bg=C_LGRAY if i%2==0 else C_WHITE
        is_total=(ln=="TOTAL")
        q.append(uc(sid,4+i,0,[row(
            [ln,desc,"="+fml if not fml.startswith("=") else fml,"2026",""],
            fmt(bg=C_DARK if is_total else bg,
                bold=is_total,fg=C_WHITE if is_total else C_TEXT))]))
    # Gross income section
    q.append(uc(sid,18,0,[row([""],sub())]))
    q.append(uc(sid,19,0,[row(["GROSS INCOME SUMMARY","","","",""],hdr(11))]))
    q.append(uc(sid,20,0,[row(["Total Gross Bookings","=SUM(Bookings!G3:G100)","","",""],
                              fmt(bg=C_LGRAY))]))
    q.append(uc(sid,21,0,[row(["Total Platform Fees Paid","=SUM(Bookings!H3:H100)","","",""],
                              fmt(bg=C_WHITE))]))
    q.append(uc(sid,22,0,[row(["Net Revenue from Rentals","=B21-B22","","",""],
                              fmt(bg=C_DARK,bold=True,fg=C_WHITE))]))
    for i,w in enumerate([80,220,130,80,200]):
        q.append(cw(sid,i,i+1,w))
    q+=[freeze(sid,2,0),tabcolor(sid,C_RED)]
    return q

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7: CLEANING & TURNOVER
# ══════════════════════════════════════════════════════════════════════════════
def tab_cleaning(sid):
    q=[]
    q.append(merge(sid,0,0,1,8))
    q.append(uc(sid,0,0,[row(
        ["🧹  CLEANING & TURNOVER LOG"]+[""]*7,hdr(11))]))
    q.append(uc(sid,1,0,[row(
        ["Date","Property","Checkout Date","Cleaner","Cost ($)",
         "Duration (hrs)","Status","Notes"],sub())]))
    samp=[
        ["2026-07-05","Property 1","2026-07-05","Maria C.",80,2.5,"Done","Deep clean"],
        ["2026-07-14","Property 2","2026-07-14","CleanTeam",120,3,"Done","Standard turnover"],
        ["2026-08-04","Property 1","2026-08-04","Maria C.",80,2.5,"Scheduled",""],
    ]
    for i,r_ in enumerate(samp): q.append(uc(sid,2+i,0,[row(r_,alt(i))]))
    for i in range(37):
        q.append(uc(sid,2+len(samp)+i,0,[row([""]*8,alt(i+len(samp)))]))
    q.append(dropdown(sid,2,100,1,2,PROPS))
    q.append(dropdown(sid,2,100,6,7,["Scheduled","In Progress","Done","Skipped"]))
    for i,w in enumerate([90,120,100,130,90,100,100,180]):
        q.append(cw(sid,i,i+1,w))
    q+=[freeze(sid,2,0),tabcolor(sid,C_LGRAY)]
    return q

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8: SUPPLIES & RESTOCK
# ══════════════════════════════════════════════════════════════════════════════
def tab_supplies(sid):
    q=[]
    q.append(merge(sid,0,0,1,7))
    q.append(uc(sid,0,0,[row(
        ["📦  SUPPLIES & RESTOCK TRACKER"]+[""]*6,hdr(11))]))
    q.append(uc(sid,1,0,[row(
        ["Item","Property","Category","Par Level","Current Stock",
         "Status","Last Restocked"],sub())]))
    samp=[
        ["Coffee pods","Property 1","Kitchen","24 pods","8 pods","Low","2026-07-01"],
        ["Shampoo (300ml)","Property 1","Bathroom","4 bottles","1 bottle","Order Now","2026-06-28"],
        ["Toilet paper (rolls)","Property 2","Bathroom","12 rolls","10 rolls","OK","2026-07-10"],
        ["Hand soap","ALL","Bathroom","6 units","3 units","Low","2026-07-05"],
        ["Laundry detergent","Property 2","Laundry","2 bottles","2 bottles","OK","2026-07-12"],
        ["Dish soap","Property 1","Kitchen","2 bottles","0 bottles","Order Now","2026-06-20"],
    ]
    for i,r_ in enumerate(samp): q.append(uc(sid,2+i,0,[row(r_,alt(i))]))
    for i in range(34):
        q.append(uc(sid,2+len(samp)+i,0,[row([""]*7,alt(i+len(samp)))]))
    q.append(dropdown(sid,2,100,1,2,PROPS_ALL))
    q.append(dropdown(sid,2,100,5,6,["OK","Low","Order Now"]))
    for i,w in enumerate([180,110,100,110,110,100,110]):
        q.append(cw(sid,i,i+1,w))
    q+=[freeze(sid,2,0),tabcolor(sid,C_LGRAY)]
    return q

# ══════════════════════════════════════════════════════════════════════════════
# MAIN — construir todo
# ══════════════════════════════════════════════════════════════════════════════
def build(spreadsheet_id: str):
    key_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS","")
    credentials = service_account.Credentials.from_service_account_file(
        key_file, scopes=SCOPES)
    service = build_service = None
    from googleapiclient.discovery import build as gapi_build
    service = gapi_build("sheets","v4",credentials=credentials)
    ss = service.spreadsheets()

    print(f"Connecting to spreadsheet: {spreadsheet_id}")
    meta = ss.get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["sheetId"] for s in meta["sheets"]]
    default_sid = meta["sheets"][0]["properties"]["sheetId"]

    tab_defs = [
        ("🏡 Setup",    SID["setup"],    C_ACNT),
        ("📅 Bookings", SID["bookings"], C_GRN),
        ("💳 Expenses", SID["expenses"], C_AMB),
        ("📊 Dashboard",SID["dashboard"],C_ACNT),
        ("📈 P&L",      SID["pl"],       C_GRN),
        ("🧾 Tax Summary",SID["tax"],    C_RED),
        ("🧹 Cleaning", SID["cleaning"], C_LGRAY),
        ("📦 Supplies", SID["supplies"], C_LGRAY),
    ]

    # Step 1: add all new sheets
    add_reqs = []
    for title, sid, color in tab_defs:
        if sid not in existing:
            add_reqs.append(addsheet(title, sid, color))
    if add_reqs:
        ss.batchUpdate(spreadsheetId=spreadsheet_id,
                       body={"requests":add_reqs}).execute()
        print(f"Created {len(add_reqs)} new sheets")
        time.sleep(1)

    # Rename existing sheet[0] to Setup if it was the default blank
    rename = [{"updateSheetProperties":{"properties":
               {"sheetId":default_sid,"title":"🏡 Setup"},
               "fields":"title"}}]
    try:
        ss.batchUpdate(spreadsheetId=spreadsheet_id,
                       body={"requests":rename}).execute()
    except Exception:
        pass

    # Step 2: populate each tab
    print("Building tabs...")
    builders = [
        (SID["setup"],    tab_setup),
        (SID["bookings"], tab_bookings),
        (SID["expenses"], tab_expenses),
        (SID["dashboard"],tab_dashboard),
        (SID["pl"],       tab_pl),
        (SID["tax"],      tab_tax),
        (SID["cleaning"], tab_cleaning),
        (SID["supplies"], tab_supplies),
    ]

    for sid, builder_fn in builders:
        reqs = builder_fn(sid)
        # chunk into batches of 50 to avoid payload limits
        for i in range(0, len(reqs), 50):
            chunk = reqs[i:i+50]
            ss.batchUpdate(spreadsheetId=spreadsheet_id,
                           body={"requests":chunk}).execute()
            time.sleep(0.3)
        print(f"  ✅ Tab SID={sid} done ({len(reqs)} requests)")

    print("\n🎉 STR Financial System built successfully!")
    print(f"   Open: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build STR Financial System")
    parser.add_argument("--id", required=True, help="Google Spreadsheet ID")
    args = parser.parse_args()
    build(args.id)
