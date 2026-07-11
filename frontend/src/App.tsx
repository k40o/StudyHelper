import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  api,
  getToken,
  onSessionExpired,
  setToken,
  type AskResponse,
  type Boss,
  type BossComplete,
  type Doc,
  type Health,
  type Profile,
  type Question,
  type SearchHit,
  type User,
} from "./api";
import Auth from "./Auth";
import { sound } from "./sound";
import { burst, floatText } from "./fx";

// Inline SVG icons (Lucide-style) — crisp, theme-aware, no emoji-as-icon.
const svgProps = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};
const Icons: Record<Tab, ReactNode> = {
  home: (
    <svg {...svgProps}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
      <path d="M9 21v-6h6v6" />
    </svg>
  ),
  library: (
    <svg {...svgProps}>
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  ),
  quiz: (
    <svg {...svgProps}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
    </svg>
  ),
  tutor: (
    <svg {...svgProps}>
      <path d="M12 2a7 7 0 0 0-7 7c0 2 1 3.5 2 4.5V17a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-3.5c1-1 2-2.5 2-4.5a7 7 0 0 0-7-7Z" />
      <path d="M9 22h6" />
    </svg>
  ),
  search: (
    <svg {...svgProps}>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  ),
};

type Tab = "home" | "library" | "quiz" | "tutor" | "search";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    onSessionExpired(() => {
      setToken(null);
      setUser(null);
    });
    if (!getToken()) {
      setCheckingSession(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setCheckingSession(false));
  }, []);

  if (checkingSession) return null;
  if (!user) return <Auth onAuthed={setUser} />;

  return <MainApp user={user} onLogout={() => { setToken(null); setUser(null); }} />;
}

function MainApp({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [tab, setTab] = useState<Tab>("home");
  const [health, setHealth] = useState<Health | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [bosses, setBosses] = useState<Boss[]>([]);
  const [battle, setBattle] = useState<Boss | null>(null);

  async function refresh() {
    try {
      setHealth(await api.health());
      setDocs(await api.documents());
      setBosses(await api.bosses());
    } catch (e) {
      console.error(e);
    }
  }
  async function refreshProfile() {
    try {
      setProfile(await api.profile());
    } catch (e) {
      console.error(e);
    }
  }
  useEffect(() => {
    refresh();
    refreshProfile();
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">📖</span>
          <div>
            <h1>Study Helper</h1>
            <p className="tagline">Turn your notes into an adventure</p>
          </div>
        </div>
        <div className="header-right">
          <MuteButton />
          <Hud profile={profile} />
          <button className="logout-btn" title={`Log out (${user.email})`} onClick={onLogout}>
            ⏻
          </button>
        </div>
      </header>

      {battle ? (
        <main className="content">
          <BossBattle
            boss={battle}
            profile={profile}
            onReward={refreshProfile}
            onExit={() => {
              setBattle(null);
              refresh();
              refreshProfile();
            }}
          />
        </main>
      ) : (
        <>
          <nav className="tabs">
            <TabButton id="home" tab={tab} setTab={setTab} label="Home" />
            <TabButton id="library" tab={tab} setTab={setTab} label="Library" />
            <TabButton id="quiz" tab={tab} setTab={setTab} label="Quiz" />
            <TabButton id="tutor" tab={tab} setTab={setTab} label="Tutor" />
            <TabButton id="search" tab={tab} setTab={setTab} label="Search" />
          </nav>

          <main className="content">
            {tab === "home" && (
              <Dashboard
                profile={profile}
                aiEnabled={!!health?.ai_enabled}
                docCount={docs.length}
                bosses={bosses}
                onFight={setBattle}
                goQuiz={() => setTab("quiz")}
              />
            )}
            {tab === "library" && <Library docs={docs} onChange={refresh} />}
            {tab === "quiz" && <Quiz docs={docs} profile={profile} onReward={refreshProfile} />}
            {tab === "tutor" && <Tutor aiEnabled={!!health?.ai_enabled} />}
            {tab === "search" && <Search aiEnabled={!!health?.ai_enabled} />}
          </main>
        </>
      )}

      <footer className="foot">
        Modules 1–6 live · AI questions · XP · hearts · streaks · spaced repetition · boss battles
      </footer>
    </div>
  );
}

// Compact game HUD in the header.
function Hud({ profile }: { profile: Profile | null }) {
  if (!profile) return <div className="hud" />;
  const pct = profile.xp_for_next ? (profile.xp_in_level / profile.xp_for_next) * 100 : 0;
  return (
    <div className="hud">
      <div className="level-chip">
        <div className="level-top">
          <span className="lvl">LVL {profile.level}</span>
          <span className="xp-num">
            {profile.xp_in_level}/{profile.xp_for_next}
          </span>
        </div>
        <div className="xp-mini">
          <div className="xp-mini-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="hud-chip" title="Day streak">🔥 {profile.current_streak}</div>
      <div className="hud-chip gold" title="Coins">🪙 {profile.coins}</div>
      <div className="hud-chip" title="Hearts">
        {"❤️".repeat(profile.hearts)}
        <span className="heart-empty">{"🤍".repeat(Math.max(0, profile.max_hearts - profile.hearts))}</span>
      </div>
    </div>
  );
}

function MuteButton() {
  const [muted, setMuted] = useState(sound.muted());
  return (
    <button
      className="mute-btn"
      title={muted ? "Unmute" : "Mute"}
      aria-label={muted ? "Unmute" : "Mute"}
      onClick={() => setMuted(sound.toggle())}
    >
      {muted ? "🔇" : "🔊"}
    </button>
  );
}

function TabButton({
  id,
  tab,
  setTab,
  label,
}: {
  id: Tab;
  tab: Tab;
  setTab: (t: Tab) => void;
  label: string;
}) {
  return (
    <button className={"tab" + (tab === id ? " active" : "")} onClick={() => setTab(id)}>
      <span className="tab-icon">{Icons[id]}</span>
      <span className="tab-label">{label}</span>
    </button>
  );
}

// --------------------------------------------------------------------------- //
// Dashboard (Home)
// --------------------------------------------------------------------------- //
function Dashboard({
  profile,
  aiEnabled,
  docCount,
  bosses,
  onFight,
  goQuiz,
}: {
  profile: Profile | null;
  aiEnabled: boolean;
  docCount: number;
  bosses: Boss[];
  onFight: (b: Boss) => void;
  goQuiz: () => void;
}) {
  if (!profile) {
    return (
      <div className="panel">
        <p className="empty">Loading your progress…</p>
      </div>
    );
  }
  const pct = profile.xp_for_next ? Math.round((profile.xp_in_level / profile.xp_for_next) * 100) : 0;
  const unlocked = profile.achievements.filter((a) => a.unlocked).length;

  return (
    <div className="panel dashboard">
      <div className="dash-hero">
        <div className="dash-level">{profile.level}</div>
        <div className="dash-hero-main">
          <h2>Level {profile.level}</h2>
          <div className="xp-bar">
            <div className="xp-fill" style={{ width: `${pct}%` }} />
          </div>
          <div className="dash-xp-label">
            {profile.xp_in_level} / {profile.xp_for_next} XP to level {profile.level + 1}
          </div>
        </div>
      </div>

      <div className="stat-grid">
        <StatTile icon="🔥" label="Streak" value={`${profile.current_streak}d`} />
        <StatTile icon="🎯" label="Accuracy" value={`${profile.accuracy}%`} />
        <StatTile icon="🪙" label="Coins" value={profile.coins} />
        <StatTile icon="❤️" label="Hearts" value={`${profile.hearts}/${profile.max_hearts}`} />
        <StatTile icon="✅" label="Correct" value={profile.correct_answers} />
        <StatTile icon="📝" label="Answered" value={profile.total_answers} />
      </div>

      {profile.due_reviews > 0 ? (
        <button className="btn review-cta" onClick={goQuiz}>
          🔁 {profile.due_reviews} {profile.due_reviews === 1 ? "question" : "questions"} due — review now
        </button>
      ) : (
        <div className="notice">
          {docCount === 0
            ? "Add study materials in the Library to begin your adventure."
            : "No reviews due. Play a quiz to earn XP and keep your streak alive!"}
        </div>
      )}

      <h3 className="section-title">⚔️ Boss Battles</h3>
      <div className="boss-list">
        {bosses.length === 0 ? (
          <div className="empty">Add materials and generate questions to summon bosses.</div>
        ) : (
          bosses.map((b) => (
            <div className={"boss-card" + (b.defeated ? " defeated" : "")} key={b.document_id}>
              <div className="boss-card-avatar">{b.defeated ? "🏆" : "👾"}</div>
              <div className="boss-card-main">
                <div className="boss-card-title">{b.title}</div>
                <div className="boss-card-meta">
                  {b.question_count} Qs · {b.max_hp} HP
                  {b.defeated ? ` · defeated ×${b.times_defeated}` : ""}
                </div>
              </div>
              <button
                className="btn small fight-btn"
                disabled={b.question_count === 0}
                onClick={() => onFight(b)}
              >
                {b.question_count === 0 ? "No Qs" : "Fight"}
              </button>
            </div>
          ))
        )}
      </div>

      <h3 className="section-title">
        Achievements ({unlocked}/{profile.achievements.length})
      </h3>
      <div className="ach-grid">
        {profile.achievements.map((a) => (
          <div key={a.key} className={"ach" + (a.unlocked ? " on" : "")} title={a.description}>
            <div className="ach-icon">{a.unlocked ? a.icon : "🔒"}</div>
            <div className="ach-name">{a.name}</div>
          </div>
        ))}
      </div>

      {!aiEnabled && (
        <div className="notice warn">AI is offline — generating questions and the tutor need the Gemini key.</div>
      )}
    </div>
  );
}

function StatTile({ icon, label, value }: { icon: string; label: string; value: string | number }) {
  return (
    <div className="stat-tile">
      <div className="tile-icon">{icon}</div>
      <div className="tile-value">{value}</div>
      <div className="tile-label">{label}</div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Boss Battle
// --------------------------------------------------------------------------- //
const BASE_DMG = 22;
const COMBO_MULT = [1, 1.4, 1.8, 2.3, 3];
function comboDamage(combo: number): number {
  return Math.round(BASE_DMG * COMBO_MULT[Math.min(combo - 1, COMBO_MULT.length - 1)]);
}

function BossBattle({
  boss,
  profile,
  onReward,
  onExit,
}: {
  boss: Boss;
  profile: Profile | null;
  onReward: () => void;
  onExit: () => void;
}) {
  const maxHearts = profile?.max_hearts ?? 5;
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [qIndex, setQIndex] = useState(0);
  const [bossHp, setBossHp] = useState(boss.max_hp);
  const [combo, setCombo] = useState(0);
  const [hearts, setHearts] = useState(profile?.hearts ?? 5);
  const [phase, setPhase] = useState<"loading" | "fighting" | "won" | "lost">("loading");
  const [hit, setHit] = useState<number | null>(null);
  const [reward, setReward] = useState<BossComplete | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const qs = await api.quiz(20, boss.document_id);
        if (!alive) return;
        if (qs.length === 0) setPhase("lost");
        else {
          setQuestions(qs);
          setPhase("fighting");
        }
      } catch {
        if (alive) setPhase("lost");
      }
    })();
    return () => {
      alive = false;
    };
  }, [boss.document_id]);

  function restart() {
    setBossHp(boss.max_hp);
    setCombo(0);
    setQIndex(0);
    setHit(null);
    setReward(null);
    setPhase(questions && questions.length ? "fighting" : "lost");
  }

  async function onAnswered(correct: boolean) {
    const q = questions![qIndex];
    let currentHearts = hearts;
    try {
      const r = await api.answer(q.id, correct);
      currentHearts = r.hearts;
      setHearts(r.hearts);
      if (r.xp_earned > 0) floatText(`+${r.xp_earned} XP`);
      onReward();
    } catch (e) {
      console.error(e);
    }

    if (correct) {
      const newCombo = combo + 1;
      setCombo(newCombo);
      const dmg = comboDamage(newCombo);
      setHit(dmg);
      window.setTimeout(() => setHit(null), 850);
      const remaining = Math.max(0, bossHp - dmg);
      setBossHp(remaining);
      if (remaining <= 0) {
        setPhase("won");
        sound.victory();
        burst(110);
        try {
          const rc = await api.completeBoss(boss.document_id);
          setReward(rc);
          onReward();
        } catch (e) {
          console.error(e);
        }
      }
    } else {
      setCombo(0);
      if (currentHearts <= 0) setPhase("lost");
    }
  }

  function next() {
    if (phase !== "fighting" || !questions) return;
    setQIndex((i) => (i + 1) % questions.length);
  }

  if (phase === "loading") {
    return (
      <div className="panel">
        <p className="empty">Summoning the boss… ⚔️</p>
      </div>
    );
  }

  if (phase === "won") {
    return (
      <div className="panel boss-result win">
        <div className="result-emoji">🏆</div>
        <h2>Boss Defeated!</h2>
        <p className="boss-sub">You bested {boss.title}.</p>
        {reward && (
          <div className="reward-row">
            <span className="reward-pill">+{reward.xp_earned} XP</span>
            <span className="reward-pill gold">+{reward.coins_earned} 🪙</span>
            {reward.leveled_up && <span className="reward-pill up">⬆ LEVEL UP!</span>}
          </div>
        )}
        <div className="boss-result-actions">
          <button className="btn" onClick={restart}>
            Fight again
          </button>
          <button className="btn small ghost" onClick={onExit}>
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  if (phase === "lost") {
    return (
      <div className="panel boss-result lose">
        <div className="result-emoji">💀</div>
        <h2>Defeated…</h2>
        <p className="boss-sub">
          {questions && questions.length
            ? "The boss survived. Regroup and try again!"
            : "This boss has no questions yet — generate some in the Library first."}
        </p>
        <div className="boss-result-actions">
          {questions && questions.length > 0 && (
            <button className="btn" onClick={restart}>
              Try again
            </button>
          )}
          <button className="btn small ghost" onClick={onExit}>
            Retreat
          </button>
        </div>
      </div>
    );
  }

  const q = questions![qIndex];
  const hpPct = Math.round((bossHp / boss.max_hp) * 100);
  return (
    <div className="battle">
      <div className="boss-stage">
        <button className="boss-exit" onClick={onExit}>
          ← Flee
        </button>
        <div className={"boss-avatar" + (hit != null ? " hurt" : "")}>👾</div>
        <div className="boss-name">{boss.title}</div>
        <div className="boss-hpbar">
          <div className="boss-hpfill" style={{ width: `${hpPct}%` }} />
          <span className="boss-hptext">
            {bossHp} / {boss.max_hp} HP
          </span>
        </div>
        <div className="battle-status">
          <span className={"combo" + (combo > 1 ? " active" : "")}>⚔ Combo x{combo}</span>
          <span className="battle-hearts">
            {"❤️".repeat(hearts)}
            <span className="heart-empty">{"🤍".repeat(Math.max(0, maxHearts - hearts))}</span>
          </span>
        </div>
        {hit != null && <div className="dmg-float">-{hit}</div>}
      </div>
      <QuestionCard
        key={q.id}
        q={q}
        index={qIndex}
        total={questions!.length}
        onAnswered={onAnswered}
        onNext={next}
      />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Library / Upload
// --------------------------------------------------------------------------- //
function Library({ docs, onChange }: { docs: Doc[]; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [warnMsg, setWarnMsg] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [uploadResults, setUploadResults] = useState<
    { name: string; ok: boolean; detail: string }[]
  >([]);
  const fileRef = useRef<HTMLInputElement>(null);

  // A Set (not a single id) so generating several documents at once doesn't
  // have one request's completion clear the "in progress" state of another.
  const [genIds, setGenIds] = useState<Set<number>>(new Set());
  const [genResults, setGenResults] = useState<{ id: number; title: string; ok: boolean; detail: string }[]>([]);

  async function onDelete(doc: Doc) {
    if (!window.confirm(`Delete "${doc.title}"? The file is moved to a trash folder.`)) return;
    setDeletingId(doc.id);
    setMsg(null);
    try {
      await api.deleteDoc(doc.id);
      setMsg(`Deleted "${doc.title}".`);
      onChange();
    } catch (e) {
      setMsg(`Error: ${(e as Error).message}`);
    } finally {
      setDeletingId(null);
    }
  }

  async function onGenerate(doc: Doc) {
    setGenIds((prev) => new Set(prev).add(doc.id));
    try {
      const r = await api.generate(doc.id, 20);
      const detail = r.quota_exceeded
        ? `+${r.generated} new (stopped — Gemini quota exceeded, try again later)`
        : `+${r.generated} new · ${r.total} total`;
      setGenResults((prev) => [
        ...prev.filter((x) => x.id !== doc.id),
        { id: doc.id, title: doc.title, ok: !r.quota_exceeded, detail },
      ]);
      onChange();
    } catch (e) {
      setGenResults((prev) => [
        ...prev.filter((x) => x.id !== doc.id),
        { id: doc.id, title: doc.title, ok: false, detail: (e as Error).message },
      ]);
    } finally {
      setGenIds((prev) => {
        const next = new Set(prev);
        next.delete(doc.id);
        return next;
      });
    }
  }

  function onGenerateAll() {
    // Fire every document's generation concurrently instead of one at a time —
    // each tracks its own progress/result independently (see genIds/genResults).
    for (const doc of docs) {
      if (!genIds.has(doc.id)) onGenerate(doc);
    }
  }

  async function onFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const queue = Array.from(files);
    setBusy(true);
    setMsg(null);
    setWarnMsg(null);
    setUploadResults([]);

    for (let i = 0; i < queue.length; i++) {
      const file = queue[i];
      setMsg(queue.length > 1 ? `Uploading ${i + 1}/${queue.length}: ${file.name}…` : `Uploading ${file.name}…`);
      try {
        const r = await api.upload(file);
        setUploadResults((prev) => [
          ...prev,
          { name: file.name, ok: true, detail: `${r.status}${r.blocks ? ` · ${r.blocks} blocks` : ""}` },
        ]);
        if (r.warning) setWarnMsg(r.warning);
      } catch (e) {
        // Keep going so one bad file in a multi-drop doesn't block the rest.
        setUploadResults((prev) => [...prev, { name: file.name, ok: false, detail: (e as Error).message }]);
      }
    }

    setMsg(null);
    onChange();
    setBusy(false);
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <div className="panel">
      <div
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          onFiles(e.dataTransfer.files);
        }}
        onClick={() => fileRef.current?.click()}
      >
        <div className="dropzone-icon">⬆️</div>
        <div className="dropzone-title">{busy ? "Importing…" : "Add study materials"}</div>
        <div className="dropzone-sub">Drop one or many files, or click · .docx .pptx .pdf .txt</div>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".docx,.pptx,.pdf,.txt,.md"
          hidden
          onChange={(e) => onFiles(e.target.files)}
        />
      </div>
      {msg && <div className="notice">{msg}</div>}
      {uploadResults.length > 0 && (
        <ul className="upload-results">
          {uploadResults.map((r, i) => (
            <li key={i} className={r.ok ? "ok" : "bad"}>
              <span className="upload-result-icon">{r.ok ? "✓" : "✗"}</span>
              <span className="upload-result-name">{r.name}</span>
              <span className="upload-result-detail">{r.detail}</span>
            </li>
          ))}
        </ul>
      )}
      {warnMsg && <div className="notice warn">{warnMsg}</div>}
      {genResults.length > 0 && (
        <ul className="upload-results">
          {genResults.map((r) => (
            <li key={r.id} className={r.ok ? "ok" : "bad"}>
              <span className="upload-result-icon">{r.ok ? "✓" : "✗"}</span>
              <span className="upload-result-name">{r.title}</span>
              <span className="upload-result-detail">{r.detail}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="section-head">
        <h2 className="section-title">Your Library ({docs.length})</h2>
        {docs.length > 1 && (
          <button
            className="btn small ghost"
            onClick={onGenerateAll}
            disabled={docs.every((d) => genIds.has(d.id))}
          >
            ✨ Generate for all
          </button>
        )}
      </div>
      {docs.length === 0 ? (
        <p className="empty">No documents yet — add some notes above to get started.</p>
      ) : (
        <ul className="doc-list">
          {docs.map((d) => (
            <li key={d.id} className="doc">
              <span className={"pill pill-" + d.source_type}>{d.source_type}</span>
              <div className="doc-main">
                <div className="doc-title">{d.title}</div>
                <div className="doc-meta">
                  {d.word_count} words · {d.blocks} blocks ·{" "}
                  <span className={d.questions ? "q-count" : ""}>{d.questions} questions</span>
                </div>
              </div>
              <button
                className="gen-btn"
                title="Generate questions"
                disabled={genIds.has(d.id)}
                onClick={() => onGenerate(d)}
              >
                {genIds.has(d.id) ? "…" : d.questions ? "＋ More" : "✨ Generate"}
              </button>
              <button
                className="delete-btn"
                title="Delete"
                disabled={deletingId === d.id}
                onClick={() => onDelete(d)}
              >
                {deletingId === d.id ? "…" : "🗑"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// AI Tutor
// --------------------------------------------------------------------------- //
function Tutor({ aiEnabled }: { aiEnabled: boolean }) {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<AskResponse | null>(null);

  async function ask() {
    if (!q.trim()) return;
    setLoading(true);
    setAnswer(null);
    try {
      setAnswer(await api.ask(q));
    } catch (e) {
      setAnswer({ text: `Error: ${(e as Error).message}`, grounded: false, sources: [] });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel">
      {!aiEnabled && <div className="notice warn">AI is offline — check your Gemini key.</div>}
      <div className="ask-row">
        <input
          className="text-input"
          placeholder="Ask anything about your materials…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
        />
        <button className="btn" onClick={ask} disabled={loading}>
          {loading ? "Thinking…" : "Ask"}
        </button>
      </div>

      {answer && (
        <div className={"answer" + (answer.grounded ? "" : " ungrounded")}>
          <p className="answer-text">{answer.text}</p>
          {answer.sources.length > 0 && (
            <div className="sources">
              <div className="sources-title">Sources</div>
              {answer.sources.map((s, i) => (
                <span className="source-chip" key={i}>
                  {s.title}
                  {s.location ? ` · ${s.location}` : ""}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Quiz
// --------------------------------------------------------------------------- //
const TYPE_LABEL: Record<string, string> = {
  multiple_choice: "Multiple Choice",
  true_false: "True / False",
  fill_blank: "Fill in the Blank",
  short_answer: "Short Answer",
  matching: "Matching",
  ordering: "Ordering",
  scenario: "Scenario",
  case_study: "Case Study",
  flashcard: "Flashcard",
  trick: "Trick Question",
};
const CHOICE_TYPES = new Set(["multiple_choice", "true_false", "trick"]);
const SELF_GRADE_TYPES = new Set(["short_answer", "scenario", "case_study", "flashcard"]);

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
function norm(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
function fuzzyEqual(a: string, b: string): boolean {
  const x = norm(a);
  const y = norm(b);
  if (!x || !y) return false;
  return x === y || x.includes(y) || y.includes(x);
}

interface Rewards {
  xp: number;
  coins: number;
  leveledUp: boolean;
  achievements: { key: string; name: string; icon: string }[];
}
const EMPTY_REWARDS: Rewards = { xp: 0, coins: 0, leveledUp: false, achievements: [] };

function Quiz({
  docs,
  profile,
  onReward,
}: {
  docs: Doc[];
  profile: Profile | null;
  onReward: () => void;
}) {
  const [docId, setDocId] = useState<number | "all">("all");
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [i, setI] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [answered, setAnswered] = useState(0);
  const [rewards, setRewards] = useState<Rewards>(EMPTY_REWARDS);

  const totalQuestions = docs.reduce((n, d) => n + d.questions, 0);
  const dueCount = profile?.due_reviews ?? 0;

  function begin(qs: Question[]) {
    setQuestions(qs);
    setI(0);
    setCorrect(0);
    setAnswered(0);
    setRewards(EMPTY_REWARDS);
  }
  async function startNew() {
    setLoading(true);
    try {
      begin(await api.quiz(10, docId === "all" ? undefined : docId));
    } finally {
      setLoading(false);
    }
  }
  async function startReview() {
    setLoading(true);
    try {
      begin(await api.dueReviews(15));
    } finally {
      setLoading(false);
    }
  }

  async function onAnswered(wasCorrect: boolean) {
    setAnswered((a) => a + 1);
    if (wasCorrect) setCorrect((c) => c + 1);
    const q = questions![i];
    try {
      const r = await api.answer(q.id, wasCorrect);
      if (r.xp_earned > 0) floatText(`+${r.xp_earned} XP`);
      if (r.leveled_up) {
        sound.levelUp();
        burst();
      }
      r.new_achievements.forEach((a) => floatText(`${a.icon} ${a.name}!`, "#22d3a3"));
      setRewards((p) => ({
        xp: p.xp + r.xp_earned,
        coins: p.coins + r.coins_earned,
        leveledUp: p.leveledUp || r.leveled_up,
        achievements: [
          ...p.achievements,
          ...r.new_achievements.map((a) => ({ key: a.key, name: a.name, icon: a.icon })),
        ],
      }));
      onReward();
    } catch (e) {
      console.error(e);
    }
  }

  if (totalQuestions === 0) {
    return (
      <div className="panel">
        <p className="empty">
          No questions yet. Go to <b>Library</b> and tap <b>✨ Generate</b> on a document first.
        </p>
      </div>
    );
  }

  if (!questions) {
    return (
      <div className="panel">
        <h2 className="section-title">Start a quiz</h2>
        <div className="quiz-setup">
          <select
            className="text-input"
            value={docId}
            onChange={(e) => setDocId(e.target.value === "all" ? "all" : Number(e.target.value))}
          >
            <option value="all">All documents ({totalQuestions} questions)</option>
            {docs
              .filter((d) => d.questions > 0)
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title} ({d.questions})
                </option>
              ))}
          </select>
          <button className="btn" onClick={startNew} disabled={loading}>
            {loading ? "…" : "Play ▶"}
          </button>
        </div>
        {dueCount > 0 && (
          <button className="btn review-btn" onClick={startReview} disabled={loading}>
            🔁 Review {dueCount} due {dueCount === 1 ? "question" : "questions"}
          </button>
        )}
      </div>
    );
  }

  if (i >= questions.length) {
    const pct = answered ? Math.round((correct / answered) * 100) : 0;
    return (
      <div className="panel quiz-results">
        <div className="result-emoji">{pct >= 80 ? "🏆" : pct >= 50 ? "👍" : "📖"}</div>
        <h2>Quiz complete!</h2>
        <p className="result-score">
          {correct} / {answered} correct
        </p>
        <div className="xp-bar">
          <div className="xp-fill" style={{ width: `${pct}%` }} />
        </div>
        <div className="reward-row">
          <span className="reward-pill">+{rewards.xp} XP</span>
          <span className="reward-pill gold">+{rewards.coins} 🪙</span>
          {rewards.leveledUp && <span className="reward-pill up">⬆ LEVEL UP!</span>}
        </div>
        {rewards.achievements.length > 0 && (
          <div className="unlocks">
            {rewards.achievements.map((a) => (
              <div className="unlock" key={a.key}>
                <span className="unlock-icon">{a.icon}</span> <b>{a.name}</b> unlocked!
              </div>
            ))}
          </div>
        )}
        <button className="btn" onClick={() => setQuestions(null)}>
          Play again
        </button>
      </div>
    );
  }

  const q = questions[i];
  return (
    <QuestionCard
      key={q.id}
      q={q}
      index={i}
      total={questions.length}
      onAnswered={onAnswered}
      onNext={() => setI((n) => n + 1)}
    />
  );
}

// One interactive question. Owns all per-question state; resets via `key`.
function QuestionCard({
  q,
  index,
  total,
  onAnswered,
  onNext,
}: {
  q: Question;
  index: number;
  total: number;
  onAnswered: (correct: boolean) => void;
  onNext: () => void;
}) {
  const [phase, setPhase] = useState<"answering" | "revealed" | "done">("answering");
  const [correct, setCorrect] = useState<boolean | null>(null);
  const [selected, setSelected] = useState<string | null>(null); // choice types
  const [text, setText] = useState(""); // typed types
  const [picked, setPicked] = useState<string[]>([]); // ordering
  const [matches, setMatches] = useState<Record<number, string>>({}); // matching

  const orderPool = useMemo(() => shuffle(q.options), [q.id]);
  const pairs = (q.answer_data.pairs as { left: string; right: string }[] | undefined) ?? [];
  const rightOptions = useMemo(() => shuffle(pairs.map((p) => p.right)), [q.id]);
  const correctOrder = (q.answer_data.correct_order as string[] | undefined) ?? [];

  function finish(wasCorrect: boolean) {
    setCorrect(wasCorrect);
    setPhase("done");
    if (wasCorrect) sound.correct();
    else sound.wrong();
    onAnswered(wasCorrect);
  }

  const isLast = index + 1 === total;

  return (
    <div className="panel">
      <div className="quiz-head">
        <span className="quiz-progress">
          Question {index + 1} / {total}
        </span>
        <span className={"type-badge diff-" + q.difficulty}>
          {TYPE_LABEL[q.question_type] ?? q.question_type}
        </span>
      </div>

      <p className="quiz-prompt">{q.prompt}</p>

      {/* ---- Multiple choice / true-false / trick ---- */}
      {CHOICE_TYPES.has(q.question_type) && (
        <div className="options">
          {q.options.map((opt) => {
            let cls = "option";
            if (phase === "done") {
              if (opt === q.answer) cls += " correct";
              else if (opt === selected) cls += " wrong";
            }
            return (
              <button
                key={opt}
                className={cls}
                disabled={phase === "done"}
                onClick={() => {
                  setSelected(opt);
                  finish(opt === q.answer);
                }}
              >
                {opt}
              </button>
            );
          })}
        </div>
      )}

      {/* ---- Fill in the blank (auto-checked) ---- */}
      {q.question_type === "fill_blank" && (
        <div className="answer-input">
          <input
            className="text-input"
            placeholder="Type your answer…"
            value={text}
            disabled={phase === "done"}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && text.trim() && finish(fuzzyEqual(text, q.answer))}
          />
          {phase !== "done" && (
            <button className="btn" disabled={!text.trim()} onClick={() => finish(fuzzyEqual(text, q.answer))}>
              Check
            </button>
          )}
        </div>
      )}

      {/* ---- Short answer / scenario / case study / flashcard (self-graded) ---- */}
      {SELF_GRADE_TYPES.has(q.question_type) && (
        <div className="self-grade">
          {q.question_type !== "flashcard" && (
            <textarea
              className="text-input quiz-textarea"
              placeholder="Write your answer, then reveal the model answer…"
              value={text}
              disabled={phase !== "answering"}
              onChange={(e) => setText(e.target.value)}
            />
          )}
          {phase === "answering" && (
            <button className="btn" onClick={() => setPhase("revealed")}>
              {q.question_type === "flashcard" ? "Flip card 🔄" : "Reveal model answer"}
            </button>
          )}
          {phase !== "answering" && (
            <>
              <div className="model-answer">
                <b>Answer:</b> {q.answer}
              </div>
              {phase === "revealed" && (
                <div className="grade-btns">
                  <span className="grade-label">How did you do?</span>
                  <button className="btn good" onClick={() => finish(true)}>
                    ✓ Got it
                  </button>
                  <button className="btn bad" onClick={() => finish(false)}>
                    ✗ Missed it
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ---- Ordering (tap to arrange) ---- */}
      {q.question_type === "ordering" && (
        <div className="ordering">
          <div className="order-slots">
            {picked.map((item, idx) => (
              <button
                key={item}
                className={
                  "order-chip picked" +
                  (phase === "done" ? (correctOrder[idx] === item ? " correct" : " wrong") : "")
                }
                disabled={phase === "done"}
                onClick={() => setPicked(picked.filter((x) => x !== item))}
              >
                <span className="order-num">{idx + 1}</span> {item}
              </button>
            ))}
            {picked.length === 0 && <span className="order-hint">Tap items below in the correct order</span>}
          </div>
          {phase !== "done" && (
            <div className="order-pool">
              {orderPool
                .filter((item) => !picked.includes(item))
                .map((item) => (
                  <button key={item} className="order-chip" onClick={() => setPicked([...picked, item])}>
                    {item}
                  </button>
                ))}
            </div>
          )}
          {phase !== "done" && picked.length === orderPool.length && (
            <button
              className="btn"
              onClick={() => finish(JSON.stringify(picked) === JSON.stringify(correctOrder))}
            >
              Check order
            </button>
          )}
          {phase === "done" && correct === false && (
            <div className="correct-order">
              Correct order: {correctOrder.map((s, idx) => `${idx + 1}. ${s}`).join("  ")}
            </div>
          )}
        </div>
      )}

      {/* ---- Matching (dropdowns) ---- */}
      {q.question_type === "matching" && (
        <div className="matching">
          {pairs.map((p, idx) => {
            const chosen = matches[idx] ?? "";
            const rowState =
              phase === "done" ? (chosen === p.right ? " correct" : " wrong") : "";
            return (
              <div className={"match-row" + rowState} key={idx}>
                <span className="match-left">{p.left}</span>
                <select
                  className="text-input"
                  value={chosen}
                  disabled={phase === "done"}
                  onChange={(e) => setMatches({ ...matches, [idx]: e.target.value })}
                >
                  <option value="">— choose —</option>
                  {rightOptions.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                {phase === "done" && chosen !== p.right && (
                  <span className="match-fix">→ {p.right}</span>
                )}
              </div>
            );
          })}
          {phase !== "done" && Object.keys(matches).length === pairs.length && (
            <button
              className="btn"
              onClick={() => finish(pairs.every((p, idx) => matches[idx] === p.right))}
            >
              Check matches
            </button>
          )}
        </div>
      )}

      {/* ---- Result footer (shared) ---- */}
      {phase === "done" && (
        <div className="reveal">
          <p className={"verdict " + (correct ? "ok" : "bad")}>
            {correct ? "✓ Correct!" : "✗ Not quite"}
          </p>
          {q.explanation && <p className="reveal-exp">{q.explanation}</p>}
          <div className="reveal-foot">
            <span className="source-chip">
              {q.source_title}
              {q.source_location ? ` · ${q.source_location}` : ""}
            </span>
            <button className="btn small" onClick={onNext}>
              {isLast ? "Finish" : "Next →"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Search
// --------------------------------------------------------------------------- //
function Search({ aiEnabled }: { aiEnabled: boolean }) {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [hits, setHits] = useState<SearchHit[] | null>(null);

  async function run() {
    if (!q.trim()) return;
    setLoading(true);
    try {
      setHits((await api.search(q)).hits);
    } catch {
      setHits([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel">
      {!aiEnabled && <div className="notice warn">AI is offline — search needs embeddings.</div>}
      <div className="ask-row">
        <input
          className="text-input"
          placeholder="Semantic search across your notes…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <button className="btn" onClick={run} disabled={loading}>
          {loading ? "…" : "Search"}
        </button>
      </div>

      {hits && hits.length === 0 && <p className="empty">No matches.</p>}
      {hits && hits.length > 0 && (
        <ul className="hit-list">
          {hits.map((h, i) => (
            <li className="hit" key={i}>
              <div className="hit-head">
                <span className="hit-title">{h.title ?? "Untitled"}</span>
                <span className="hit-loc">
                  {h.slide != null ? `slide ${h.slide}` : h.page != null ? `page ${h.page}` : ""}
                </span>
                <span className="hit-score">{Math.round(h.score * 100)}%</span>
              </div>
              <p className="hit-text">{h.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
