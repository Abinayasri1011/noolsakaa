# streamlit_book_recommender.py —  Nool Sakā “book-buddy”
# ---------------------------------------------------------------------------
# pastel wallpaper · interactive placeholders · enlarged QR listing all recos 1-N
# ranking: same-author → Indian-genre → Tamil-genre → Foreign-genre
# ---------------------------------------------------------------------------

from pathlib import Path
from typing import List
import difflib, io, pandas as pd, streamlit as st
from streamlit_searchbox import st_searchbox      # autosuggest component
import qrcode                                     # QR generator
from PIL import Image                             # for resizing

# ───────────────────────── 1 • PAGE STYLE ─────────────────────────
st.set_page_config("📚 Nool Sakā — Your Book Buddy", "📖", layout="wide")
st.markdown("""
<style>
html,body,.stApp {
  background: #FFF9C4;
  color: #111;
  font-family: 'Segoe UI', sans-serif;
}
body:before {
  content: '';
  position: fixed;
  inset: 0;
  background: url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iI0ZGRUIwMCIgZD0iTTcgMkgyMXYxOC03SDBaIi8+PC9zdmc+") repeat;
  opacity: .25;
  pointer-events: none;
  z-index: -2;
}
body:after {
  content: '';
  position: fixed;
  inset: 0;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60'><text x='50%' y='50%' text-anchor='middle' dominant-baseline='middle' font-size='48'>📚</text></svg>") repeat;
  background-size: 120px 120px;
  opacity: .12;
  pointer-events: none;
  z-index: -1;
}
.hero-main {
  position: relative;
  background: #FFC400;
  color: #000;
  font-size: 2.4rem;
  font-weight: 800;
  text-align: center;
  padding: 1rem 0;
  margin: -2rem -2rem 0;
}
.hero-main:after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: .15;
  pointer-events: none;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80'><text x='50%' y='50%' text-anchor='middle' dominant-baseline='middle' font-size='64'>📚</text></svg>") repeat;
  background-size: 80px 80px;
}
.hero-sub {
  background: #FFFDE7;
  color: #000;
  font-size: 1.3rem;
  font-weight: 600;
  text-align: center;
  padding: .6rem 0;
  margin: 0 -2rem;
}
.footer-credit {
  text-align: right;
  font-size: .95rem;
  font-weight: 600;
  color: #333;
  margin: .4rem 0 3rem;
}
section[data-testid="stSidebar"] > div:first-child {
  background: #ECEFF1;
}
.section-header {
  background: #A9A9A9;
  color: #000000;
  padding: .8rem 1rem;
  font-weight: 600;
  border-radius: 10px;
}
.stDataFrame {
  background: #fff!important;
  border: 3px solid #FFC400;
  border-radius: 12px;
}
button[kind="primary"] {
  border-radius: 12px;
  font-weight: 800;
  background: #FFC400;
  border: none;
  color: #000;
  padding: .45rem 1.2rem;
}
button[kind="primary"]:hover {
  filter: brightness(110%);
  transform: translateY(-2px);
}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero-main">📚 BOOK RECOMMENDER</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Nool Sakā — Your Pudhaga Buddy!</div>', unsafe_allow_html=True)
st.markdown('<p class="footer-credit">Powered by Black Board Learning</p>', unsafe_allow_html=True)
celebrate = lambda: st.balloons()

# ───────────────────────── 2 • DATA LOADER ───────────────────────
DEFAULT_PATH = Path("Book List1.csv")

@st.cache_data(show_spinner=False)
def load_dataset(path: Path) -> pd.DataFrame:
    def canonical(df: pd.DataFrame) -> pd.DataFrame:
        clean = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
        alias = lambda *alts: next((clean[a] for a in alts if a in clean), None)
        rename = {}
        for canon, alts in {
            "Book Name": ("bookname","book","title"),
            "Author":    ("author","authors"),
            "Genre":     ("genre","category")
        }.items():
            key = alias(*alts)
            if not key:
                raise ValueError(f"Missing {canon} column")
            rename[key] = canon

        rating = alias("averageratings","averagerating","avg")
        count  = alias("totalratings","numberofratings","ratingscount")
        nat    = alias("nationality","country","origin")

        if rating:
            rename[rating] = "Average Rating"
            df[rating] = pd.to_numeric(df[rating], errors="coerce").fillna(0).round(2)
        else:
            df["Average Rating"] = 0.0

        if count:
            rename[count] = "Number of Ratings"
            df[count] = pd.to_numeric(df[count], errors="coerce").fillna(0).astype(int)
        else:
            df["Number of Ratings"] = 0

        if nat:
            rename[nat] = "Nationality"

        # preserve any extra columns like Stall Number and Publisher
        return df.rename(columns=rename)

    raw = pd.read_excel(path) if path.suffix.lower()==".xlsx" else pd.read_csv(path, encoding="latin1")
    df  = canonical(raw).fillna("")
    df["_title_lc"]  = df["Book Name"].str.lower().str.strip()
    df["_author_lc"] = df["Author"].str.lower().str.strip()
    return df

# ───────────────────────── 3 • MATCH & RESOLVE ───────────────────
def resolve(df: pd.DataFrame, text: str) -> pd.Series:
    frag      = text.lower().strip()
    by_author = df[df["_author_lc"].str.contains(frag)]
    if len(by_author):
        return by_author.iloc[0]
    by_title = df[df["_title_lc"].str.contains(frag)]
    if len(by_title):
        return by_title.iloc[0]
    combos = (df["_title_lc"]+"|"+df["_author_lc"]).tolist()
    best   = difflib.get_close_matches(frag, combos, 1, 0.3)
    if not best:
        st.error(f"No close match for '{text}'."); st.stop()
    return df[(df["_title_lc"]+"|"+df["_author_lc"])==best[0]].iloc[0]

# ───────────────────────── 4 • RECOMMENDER ───────────────────────
def recommend(df: pd.DataFrame, favs: List[pd.Series], top: int = 10) -> pd.DataFrame:
    df = df.copy()
    df["Is Indian"] = df["Author"].str.lower().str.contains("|".join([
        "tagore","narayan","desai","nair","mistry","gosh","bhagat","murthy","rao","sahni"
    ]))
    df["Is Tamil"]  = df["Author"].str.lower().str.contains("|".join([
        "kalki","jeyamohan","vaasan","vairamuthu","sivashankari","sujatha",
        "imbam","charu","nivedita","imayam","magan","ananth","pandian"
    ]))

    fav_idx = {r.name for r in favs}
    authors = {r["Author"] for r in favs}
    genres  = {r["Genre"] for r in favs if r.get("Genre")}

    same_author = pd.concat([
        df[(df["Author"]==a)&(~df.index.isin(fav_idx))]
          .nlargest(3, ["Average Rating","Number of Ratings"])
        for a in authors
    ], ignore_index=False) if authors else pd.DataFrame()

    pool    = df[(df["Genre"].isin(genres)) & (~df.index.isin(fav_idx|set(same_author.index)))]
    indian  = pool[(pool["Is Indian"]) & (~pool["Is Tamil"])]
    tamil   = pool[pool["Is Tamil"]]
    foreign = pool[~pool["Is Indian"]]

    ranked = pd.concat([
        same_author,
        indian.nlargest(top,   ["Average Rating","Number of Ratings"]),
        tamil.nlargest(top,    ["Average Rating","Number of Ratings"]),
        foreign.nlargest(top,  ["Average Rating","Number of Ratings"]),
    ], ignore_index=False)

    if len(ranked) < top:
        rest = df[~df.index.isin(ranked.index)]
        ranked = pd.concat([
            ranked,
            rest[(rest["Is Indian"]) & (~rest["Is Tamil"])].nlargest(top, ["Average Rating","Number of Ratings"]),
            rest[rest["Is Tamil"]].nlargest(top, ["Average Rating","Number of Ratings"]),
            rest[~rest["Is Indian"]].nlargest(top, ["Average Rating","Number of Ratings"]),
        ], ignore_index=False)

    return ranked.drop_duplicates("Book Name").head(top)

# ───────────────────────── 5 • SIDEBAR ─────────────────
# NOTE: we silently load the default dataset so df / options exist.
df = load_dataset(DEFAULT_PATH)
options = sorted(set(df["Book Name"]) | set(df["Author"]))

st.sidebar.header("🎯 1 | Pick how many recos")

# 5-A • How many recommendations?
rec_cnt = st.sidebar.slider("Suggestions wanted", 5, 25, 10, 1)
st.session_state["rec_cnt"] = rec_cnt
st.sidebar.markdown(
    f"<p style='margin-top:-0.5rem;'>🔢 "
    f"<span style='background:#FFC400;padding:2px 6px;border-radius:6px;"
    f"font-weight:600'>{rec_cnt}</span> will be generated</p>",
    unsafe_allow_html=True,
)

# 5-B • Optional accent colour
st.sidebar.header("🎨 2 | Card tint")
card_color = st.sidebar.color_picker("Pick a light colour", "#F5F5F5")
st.session_state["card_color"] = card_color  # used in Section 7

# 5-C • Safe rerun helper (Streamlit ≥1.37 uses st.rerun)
def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

# 5-D • Reset button — wipes all state incl. search-box inputs
st.sidebar.header("🔄 3 | Start over")
if st.sidebar.button("Reset selections"):
    for key in (
        "favs_rows", "favs_raw", "recs_df", "rec_idx",
        "stored_rec_cnt", "pick1", "pick2", "pick3"
    ):
        st.session_state.pop(key, None)
    safe_rerun()

# ───────────────────────── 6 • INTERACTIVE INPUTS ───────────────
st.markdown('<div class="section-header">🤗 Hey buddy! Pick up to 3 books/authors you love:</div>', unsafe_allow_html=True)

def sugg(term: str) -> list[str]:
    if not term:
        return []
    term = term.lower()
    return [o for o in options if term in o.lower()][:30]

favs  = []
pick1 = st_searchbox(sugg, placeholder="🤔 What's got you hooked right now?", key="pick1")
if pick1:
    favs.append(pick1)
    pick2 = st_searchbox(sugg, placeholder="🔍 Got another fav? Share it!", key="pick2")
else:
    pick2 = None
if pick2:
    favs.append(pick2)
    pick3 = st_searchbox(sugg, placeholder="🎯 One last pick to seal the deal?", key="pick3")
else:
    pick3 = None
if pick3:
    favs.append(pick3)

# helper line — centered & bold
st.markdown(
    """
    <p style="
        text-align:center;
        font-size:0.95rem;
        font-weight:700;           /* bold */
        color:#555;
        margin-top:0.5rem;">
        The more you share, the sharper your recos become! 😉
    </p>
    """,
    unsafe_allow_html=True
)
# ───────────────────────── 7 • ACTION & OUTPUTS ──────────────────
def build_qr_payload(df_out: pd.DataFrame) -> str:
    return "\n".join(
        f"{i}. {r['Book Name']} — {r['Author']} — Stall {r['Stall Number']}"
        for i, (_, r) in enumerate(df_out.iterrows(), 1)
    )[:4200]


def compute_recs():
    n_recs   = st.session_state.get("rec_cnt", 10)
    fav_rows = st.session_state.get("favs_rows", [])
    if not fav_rows:
        st.warning("Buddy, pick at least one favourite first!")
        return
    recs_df = (
        recommend(df, fav_rows, n_recs)
        [["Book Name", "Author", "Stall Number"]]
        .reset_index(drop=True)
    )
    st.session_state.update(
        recs_df=recs_df,
        stored_rec_cnt=n_recs,
        rec_idx=0
    )

# 🚀 button
if st.button("🚀 Get my recos!", use_container_width=True):
    st.session_state["favs_rows"] = [resolve(df, x) for x in favs]
    st.session_state["favs_raw"]  = favs
    compute_recs()
    celebrate()

st.markdown("<div style='margin-top:1.2rem;'></div>", unsafe_allow_html=True)

# recompute if slider changed
if st.session_state.get("recs_df") is not None:
    if st.session_state.get("stored_rec_cnt") != st.session_state["rec_cnt"]:
        compute_recs()

# ───────── render ─────────
if "recs_df" in st.session_state:
    fav_rows   = st.session_state["favs_rows"]
    raw_picks  = st.session_state["favs_raw"]
    recs_df    = st.session_state["recs_df"]
    card_color = st.session_state.get("card_color", "#F5F5F5")

    st.markdown(
        '<div class="section-header">✨ Your custom picks are here!</div>',
        unsafe_allow_html=True
    )

    # trim top gap + add column separator
    st.markdown("""
        <style>
          div[data-testid="column"]:first-child{
              border-right:1px solid #BBB;
              margin-right:.5rem;padding-right:.5rem;}
        </style>""",
        unsafe_allow_html=True
    )

    left_pane, right_pane = st.columns([1, 2], gap="small")

    # ① LEFT – picks list
    with left_pane:
        st.markdown(
            """<h2 style="
                font-size: 1.6rem;        /* enlarged */
                background: #FFE082;      /* highlight */
                padding: 4px 10px;
                border-radius: 6px;
                margin: 0 0 .4rem 0;">Your picks</h2>""",
            unsafe_allow_html=True
        )
        for i, (raw, row) in enumerate(zip(raw_picks, fav_rows), 1):
            if raw.lower() in row["Author"].lower():
                st.write(f"{i}. **{row['Author']}**")
            else:
                st.write(f"{i}. **{row['Book Name']}**  \n{row['Author']}")

    # ② RIGHT – recommendations carousel
    with right_pane:
        VISIBLE, STEP = 3, 3
        total = len(recs_df)
        idx   = st.session_state.get("rec_idx", 0) % max(total, 1)
        end   = min(idx + VISIBLE, total)

        st.markdown(f"""
            <h3 style="
              font-size: 1.6rem;        /* reduced */
              background: #FFE082;      /* highlight */
              padding: 4px 10px;
              border-radius: 6px;
              text-align: center;
              margin: 0 0 .5rem 0;">
              📖 Showing {idx+1} – {end} of 🎉 {total} Recommendations
            </h3>""", unsafe_allow_html=True)

        first, last = idx == 0, idx + STEP >= total
        prev_b, next_b = st.columns(2)
        with prev_b:
            st.button("◀ Prev", disabled=first, use_container_width=True,
                      on_click=lambda: st.session_state.update(rec_idx=max(idx-STEP, 0)))
        with next_b:
            st.button("Next ▶", disabled=last, use_container_width=True,
                      on_click=lambda: st.session_state.update(rec_idx=min(idx+STEP, total - VISIBLE)))

        if st.session_state["rec_idx"] != idx:
            st.rerun()

        for _, row in recs_df.iloc[idx:end].iterrows():
            st.markdown(f"""
              <div style="
                background: {card_color};
                border-radius: 8px;
                padding: 0.6rem 0.8rem;
                margin-bottom: 0.45rem;">
                <b>{row['Book Name']}</b><br>
                {row['Author']}<br>
                <small>Stall No: {row['Stall Number']}</small>
              </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # CSV + QR
        c1, c2 = st.columns(2, gap="small")
        with c1:
            st.download_button(
                "⬇️ CSV",
                recs_df.to_csv(index=False).encode(),
                "noolsaka_recs.csv",
                "text/csv"
            )
        with c2:
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=12,
                border=4
            )
            qr.add_data(build_qr_payload(recs_df))
            qr.make(fit=True)
            buf = io.BytesIO()
            qr.make_image(fill_color="black", back_color="white")\
               .resize((260, 260), Image.NEAREST).save(buf, "PNG")
            st.image(buf.getvalue(), caption="📱 Scan your list", width=260)
            st.download_button(
                "⬇️ QR PNG",
                buf.getvalue(),
                "noolsaka_recs.png",
                "image/png"
            )