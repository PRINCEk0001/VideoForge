import { useState, useRef, useEffect } from "react";
import Layout from "./components/Layout";
import "./index.css";

// All 11 pipeline phases — shown as simple steps to the user
const STEPS = [
  { id: 1, icon: "📈", label: "Analyzing trends" },
  { id: 2, icon: "🎯", label: "Selecting best topic" },
  { id: 3, icon: "✍️", label: "Writing script" },
  { id: 4, icon: "🎬", label: "Planning scenes" },
  { id: 5, icon: "🖼️", label: "Finding footage" },
  { id: 6, icon: "✅", label: "Validating content" },
  { id: 7, icon: "🎙️", label: "Generating voiceover" },
  { id: 8, icon: "🏗️", label: "Structuring video" },
  { id: 9, icon: "⚖️", label: "Compliance check" },
  { id: 10, icon: "🔍", label: "Optimizing SEO" },
  { id: 11, icon: "🎞️", label: "Assembling final video" },
];

const SCENE_OPTIONS = [3, 5, 8, 10];
const FORMAT_OPTIONS = [
  { id: "16:9", label: "Long-Form (16:9)", icon: "📺" },
  { id: "9:16", label: "Shorts (9:16)", icon: "📱" },
];
const STYLE_OPTIONS = [
  { id: "realistic", label: "Realistic", icon: "📸" },
  { id: "cartoon", label: "Animated Cartoon", icon: "🎨" },
];
const VOICE_PROVIDERS = [
  { id: "edge", label: "Fast & Free", icon: "⚡" },
  { id: "kokoro", label: "Local HD (Free)", icon: "🏠" },
  { id: "eleven", label: "Premium (AI)", icon: "✨" },
];

const VOICE_CATALOG = {
  edge: [
    { id: "en-US-AvaNeural", label: "Ava", gender: "female" },
    { id: "en-US-AndrewNeural", label: "Andrew", gender: "male" },
    { id: "en-US-EmmaNeural", label: "Emma", gender: "female" },
    { id: "en-US-BrianNeural", label: "Brian", gender: "male" },
  ],
  kokoro: [
    { id: "af_heart", label: "Heart", gender: "female" },
    { id: "bm_george", label: "George", gender: "male" },
  ],
  eleven: [
    { id: "21m00Tcm4TlvDq8ikWAM", label: "Rachel", gender: "female" },
    { id: "pNInz6obpgDQGcFmaJgB", label: "Adam", gender: "male" },
    { id: "TxGEqnHW47ic4qpgms3u", label: "Josh", gender: "male" },
  ],
};
const MEDIA_BALANCE_LABELS = [
  { value: 0.0, label: "100% AI (Creative)" },
  { value: 0.5, label: "Balanced (Hybrid)" },
  { value: 1.0, label: "100% Stock (Realism)" },
];

/* ── tiny helpers ─────────────────────────────────────────── */
function fmtDur(secs) {
  if (!secs) return "—";
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/* ── Step row ─────────────────────────────────────────────── */
function StepRow({ icon, label, status }) {
  return (
    <div className={`step-row ${status}`}>
      <span className="step-icon">{icon}</span>
      <span className="step-name">{label}</span>
      {status === "running" && <span className="spin" />}
      {status === "done" && <span className="step-status">✓ done</span>}
      {status === "error" && <span className="step-status">✗ error</span>}
      {status === "pending" && <span className="step-status">waiting</span>}
    </div>
  );
}

/* ── Main App ─────────────────────────────────────────────── */
export default function App() {
  const [topic, setTopic] = useState("");
  const [scriptSource, setScriptSource] = useState("ai"); // ai | user
  const [userScript, setUserScript] = useState("");
  const [sceneCount, setSceneCount] = useState(5);
  const [targetDuration, setTargetDuration] = useState(0);
  const [format, setFormat] = useState("16:9");
  const [voiceProvider, setVoiceProvider] = useState("edge");
  const [voiceId, setVoiceId] = useState("en-US-AvaNeural");
  const [voiceSpeed, setVoiceSpeed] = useState(1.05);
  const [videoStyle, setVideoStyle] = useState("realistic");
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [mediaBalance, setMediaBalance] = useState(0.5);
  const [state, setState] = useState("idle"); // idle | running | done | error
  const [steps, setSteps] = useState(
    STEPS.map(s => ({ ...s, status: "pending" }))
  );
  const [finalData, setFinalData] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [currentStep, setCurrentStep] = useState(1);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeView, setActiveView] = useState("generator"); // generator | videos | analytics
  const [userKeys, setUserKeys] = useState({
    gemini_api: "",
    groq_api: "",
    pexels_api: "",
    pixabay_api: "",
    elevenlabs_api: "",
    unreal_speech_api: "",
  });
  const [verifyStatus, setVerifyStatus] = useState({}); // { [key]: 'pending' | 'verifying' | 'success' | 'failed' }
  const [projects, setProjects] = useState([]);
  const [stats, setStats] = useState({ total_videos: 0, avg_retention: "0%", avg_seo: 0, total_duration_mins: 0, history: [] });
  const [isLoading, setIsLoading] = useState(false);
  const esRef = useRef(null);

  // Load masked keys on mount
  useEffect(() => {
    fetch("/api/config/keys")
      .then(r => r.json())
      .then(data => setUserKeys(prev => ({ ...prev, ...data })))
      .catch(err => console.error("Failed to load keys:", err));
  }, []);

  // Fetch projects when view changes
  useEffect(() => {
    if (activeView === "videos") {
      setIsLoading(true);
      fetch("/api/projects")
        .then(r => r.json())
        .then(data => {
          setProjects(data);
          setIsLoading(false);
        })
        .catch(err => setIsLoading(false));
    } else if (activeView === "analytics") {
      fetch("/api/analytics")
        .then(r => r.json())
        .then(data => setStats(data))
        .catch(err => console.error(err));
    }
  }, [activeView]);

  const completedCount = steps.filter(s => s.status === "done").length;
  const progress = Math.round((completedCount / STEPS.length) * 100);

  // Auto-switch to AI-Only when Cartoon is selected
  const prevStyle = useRef(videoStyle);
  if (videoStyle !== prevStyle.current) {
    if (videoStyle === "cartoon") {
      setMediaBalance(0.0);
    }
    prevStyle.current = videoStyle;
  }

  /* ── Start pipeline ──────────────────────────────────────── */
  const handleGenerate = async () => {
    if (state === "running") return;

    // API Key Validation
    const hasLLM = userKeys.gemini_api || userKeys.groq_api;
    const hasMedia = userKeys.pexels_api || userKeys.pixabay_api;
    
    if (!hasLLM || !hasMedia) {
      alert("⚠️ Required API keys are missing! Please add Gemini/Groq and Pexels/Pixabay keys in Settings first.");
      setIsSettingsOpen(true);
      return;
    }

    setState("running");
    setErrorMsg("");
    setFinalData(null);
    setSteps(STEPS.map(s => ({ ...s, status: "pending" })));
    setCurrentStep(3);

    const params = new URLSearchParams({
      topic_hint: topic.trim(),
      target_scene_count: sceneCount,
      target_duration_minutes: targetDuration,
      video_format: format,
      voice_provider: voiceProvider,
      voice_id: voiceId,
      voice_speed: voiceSpeed,
      user_script: scriptSource === "user" ? userScript.trim() : "",
      media_balance: mediaBalance,
      video_style: videoStyle,
    });
    const es = new EventSource(`/api/run?${params}`);
    esRef.current = es;

    es.addEventListener("phase_update", (e) => {
      const data = JSON.parse(e.data);
      setSteps(prev =>
        prev.map(s => s.id === data.phase ? { ...s, status: data.status } : s)
      );
    });

    es.addEventListener("pipeline_complete", (e) => {
      const data = JSON.parse(e.data);
      setFinalData(data.final_output || data);
      setState("done");
      setCurrentStep(4);
      es.close();
    });

    es.addEventListener("pipeline_failed", (e) => {
      const data = JSON.parse(e.data);
      setErrorMsg(`Phase ${data.phase} failed: ${data.reason}`);
      setState("error");
      es.close();
    });

    es.onerror = () => {
      setErrorMsg("Connection lost — make sure the backend is running.");
      setState("error");
      es.close();
    };
  };

  /* ── Play Voice Sample ──────────────────────────────────── */
  const handlePlaySample = async (vId) => {
    if (isPreviewing) return;
    setIsPreviewing(true);
    try {
      const url = `/api/voice_preview?provider=${voiceProvider}&voice_id=${vId}&speed=${voiceSpeed}`;
      const audio = new Audio(url);
      audio.onended = () => setIsPreviewing(false);
      audio.onerror = () => {
        setIsPreviewing(false);
        alert("Failed to load voice sample. Ensure dependencies are installed.");
      };
      await audio.play();
    } catch (err) {
      setIsPreviewing(false);
      console.error(err);
    }
  };

  /* ── Download video ──────────────────────────────────────── */
  const handleDownload = (projectId = null) => {
    const a = document.createElement("a");
    a.href = projectId ? `/api/projects/${projectId}/video` : "/api/download_video";
    a.download = projectId ? `video_${projectId}.mp4` : "my_video.mp4";
    a.click();
  };

  /* ── Reset ───────────────────────────────────────────────── */
  const handleReset = () => {
    esRef.current?.close();
    setState("idle");
    setSteps(STEPS.map(s => ({ ...s, status: "pending" })));
    setFinalData(null);
    setErrorMsg("");
    setCurrentStep(1);
  };

  const isRunning = state === "running";
  const isDone = state === "done";
  const isError = state === "error";

  const handleVerifyKey = async (provider, key) => {
    if (!key || key.includes("...")) return; // Don't verify masked or empty
    setVerifyStatus(prev => ({ ...prev, [provider]: 'verifying' }));
    try {
      const r = await fetch(`/api/config/verify?provider=${provider}&key=${key}`);
      const data = await r.json();
      setVerifyStatus(prev => ({ ...prev, [provider]: data.ok ? 'success' : 'failed' }));
      if (!data.ok) alert(data.message);
    } catch (err) {
      setVerifyStatus(prev => ({ ...prev, [provider]: 'failed' }));
    }
  };

  const handleSaveSettings = async () => {
    try {
      // Filter out masked keys (those with ...)
      const cleanKeys = {};
      Object.entries(userKeys).forEach(([k, v]) => {
        if (v && !v.includes("...")) cleanKeys[k] = v;
      });

      const r = await fetch("/api/config/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cleanKeys),
      });
      if (r.ok) {
        alert("Settings saved successfully (Keys are encrypted)!");
        setIsSettingsOpen(false);
      }
    } catch (err) {
      alert("Failed to save settings.");
    }
  };

  return (
    <Layout 
      onSettingsClick={() => setIsSettingsOpen(true)}
      activeView={activeView}
      onViewChange={setActiveView}
    >
      <div className="forge-container">

      {/* ── GENERATOR VIEW ──────────────────────────────────── */}
      {activeView === "generator" && (
        <>
      
      {/* API Key Warning Banner */}
      {(!(userKeys.gemini_api || userKeys.groq_api) || !(userKeys.pexels_api || userKeys.pixabay_api)) && state === "idle" && (
        <div className="section-card" style={{ border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.05)', marginBottom: '32px', cursor: 'pointer' }} onClick={() => setIsSettingsOpen(true)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <span style={{ fontSize: '24px' }}>⚠️</span>
            <div>
              <div style={{ color: '#fca5a5', fontWeight: '700', fontSize: '15px' }}>Action Required: Missing API Keys</div>
              <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>Add your Gemini/Groq and Pexels/Pixabay keys in <span style={{ textDecoration: 'underline', color: 'var(--text-main)' }}>Settings</span> to enable video generation.</div>
            </div>
          </div>
        </div>
      )}

      {/* Hero */}
      {state === "idle" && (
        <section className="hero">
          <h1 className="float">
            Elevate your content with<br />
            <span className="serif">AI-powered video</span>
          </h1>
          <p>Create high-retention, professional videos in minutes. Let our 16-agent autonomous pipeline handle everything from script to final assembly.</p>
          
          <div className="trust-bar">
            <span className="trust-logo">YOUTUBE</span>
            <span className="trust-logo">PRODUCT HUNT</span>
            <span className="trust-logo">TIKTOK</span>
            <span className="trust-logo">VIMEO</span>
          </div>
        </section>
      )}

      {/* Form Area */}
      {state === "idle" && (
        <div className="form-grid">
          
          {/* Step Indicator */}
          <div className="step-indicator">
            <div className={`step-dot ${currentStep === 1 ? 'active' : 'completed'}`}></div>
            <div className={`step-dot ${currentStep === 2 ? 'active' : (currentStep > 2 ? 'completed' : '')}`}></div>
            <div className={`step-dot ${currentStep === 3 ? 'active' : (currentStep > 3 ? 'completed' : '')}`}></div>
            <div className={`step-dot ${currentStep === 4 ? 'active' : ''}`}></div>
          </div>

          {/* STEP 1: SCRIPT & CONTENT */}
          {currentStep === 1 && (
            <div className="section-card">
              <div className="section-title">
                Step 01 <span className="serif">Script & Content</span>
              </div>
              <div>
                <div className="field-label">Content Source</div>
                <div className="scene-chips">
                  <button className={`chip ${scriptSource === 'ai' ? 'active' : ''}`} onClick={() => setScriptSource('ai')}>✨ AI Generated</button>
                  <button className={`chip ${scriptSource === 'user' ? 'active' : ''}`} onClick={() => setScriptSource('user')}>✍️ Paste My Own</button>
                </div>
              </div>

              {scriptSource === 'ai' ? (
                <div>
                  <div className="field-label">Topic or Prompt</div>
                  <textarea 
                    className="topic-input"
                    placeholder="e.g. Top 5 ways to earn passive income with AI tools in 2025..."
                    rows={3}
                    value={topic}
                    onChange={e => setTopic(e.target.value)}
                  />
                </div>
              ) : (
                <div>
                  <div className="field-label">Full Script Content</div>
                  <textarea 
                    className="topic-input"
                    placeholder="Paste your script here..."
                    rows={5}
                    value={userScript}
                    onChange={e => setUserScript(e.target.value)}
                  />
                </div>
              )}

              <div style={{ marginTop: '16px' }}>
                <div className="field-label">Target Duration: <span className="serif" style={{ fontSize: '18px', textTransform: 'none', color: 'var(--text-main)' }}>{targetDuration === 0 ? "Auto" : `${targetDuration} min`}</span></div>
                
                <div className="range-container">
                  <input 
                    type="range" 
                    min="0" 
                    max="11" 
                    step="1" 
                    className="custom-range"
                    value={targetDuration} 
                    onChange={e => setTargetDuration(parseInt(e.target.value))} 
                  />
                  <div className="range-labels">
                    <span onClick={() => setTargetDuration(0)} className={targetDuration === 0 ? 'active' : ''}>Auto</span>
                    <span onClick={() => setTargetDuration(1)} className={targetDuration === 1 ? 'active' : ''}>1m</span>
                    <span onClick={() => setTargetDuration(5)} className={targetDuration === 5 ? 'active' : ''}>5m</span>
                    <span onClick={() => setTargetDuration(11)} className={targetDuration === 11 ? 'active' : ''}>11m</span>
                  </div>
                </div>
              </div>

              <button 
                className="btn-generate" 
                onClick={() => setCurrentStep(2)}
                disabled={scriptSource === 'ai' ? !topic.trim() : !userScript.trim()}
              >
                Next Step: Audio & Voice →
              </button>
            </div>
          )}

          {/* STEP 2: ASSETS (Audio & Video Settings) */}
          {currentStep === 2 && (
            <div className="section-card">
              <div className="section-title">
                Step 02 <span className="serif">Audio & Visual Assets</span>
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                {/* Audio Column */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div>
                    <div className="field-label">Voice Provider</div>
                    <div className="scene-chips">
                      {Object.keys(VOICE_CATALOG).map(p => (
                        <button 
                          key={p}
                          className={`chip ${voiceProvider === p ? 'active' : ''}`} 
                          onClick={() => {
                            setVoiceProvider(p);
                            setVoiceId(VOICE_CATALOG[p][0].id);
                          }}
                        >
                          {p === 'edge' ? '⚡ Fast' : (p === 'kokoro' ? '🏠 Local' : '✨ Premium')}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="field-label">Speech Speed ({voiceSpeed}x)</div>
                    <input type="range" min="0.8" max="1.5" step="0.05" value={voiceSpeed} onChange={e => setVoiceSpeed(parseFloat(e.target.value))} />
                  </div>
                  <div>
                    <div className="field-label">Select Voice</div>
                    <div className="scene-chips" style={{ flexWrap: 'wrap', gap: '8px' }}>
                      {VOICE_CATALOG[voiceProvider].map(v => (
                        <button 
                          key={v.id} 
                          className={`chip ${voiceId === v.id ? "active" : ""}`} 
                          onClick={() => setVoiceId(v.id)}
                          style={{ paddingRight: "40px", position: "relative" }}
                        >
                          {v.gender === 'female' ? '👩' : '👨'} {v.label}
                          <button className="preview-btn" onClick={(e) => { e.stopPropagation(); handlePlaySample(v.id); }}>▶️</button>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Video Column */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div>
                    <div className="field-label">Visual Style</div>
                    <div className="scene-chips">
                      <button className={`chip ${videoStyle === 'realistic' ? 'active' : ''}`} onClick={() => setVideoStyle('realistic')}>🏙️ Realistic</button>
                      <button className={`chip ${videoStyle === 'cartoon' ? 'active' : 'cartoon-active'}`} onClick={() => setVideoStyle('cartoon')}>🎨 Cartoon</button>
                    </div>
                  </div>
                  <div>
                    <div className="field-label">Video Format</div>
                    <div className="scene-chips">
                      <button className={`chip ${format === '16:9' ? 'active' : ''}`} onClick={() => setFormat('16:9')}>📺 16:9</button>
                      <button className={`chip ${format === '9:16' ? 'active' : ''}`} onClick={() => setFormat('9:16')}>📱 9:16</button>
                    </div>
                  </div>
                  <div>
                    <div className="field-label">Media Mix: {MEDIA_BALANCE_LABELS.find(l => Math.abs(l.value - mediaBalance) < 0.1)?.label || "Balanced"}</div>
                    <input type="range" min="0" max="1" step="0.1" value={mediaBalance} onChange={e => setMediaBalance(parseFloat(e.target.value))} />
                  </div>
                </div>
              </div>

              <div className="btn-group" style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                <button className="btn-new" style={{ flex: 1 }} onClick={() => setCurrentStep(1)}>← Back</button>
                <button 
                  className={`btn-generate ${videoStyle === 'cartoon' ? 'cartoon-btn' : ''}`} 
                  style={{ flex: 2 }}
                  onClick={handleGenerate}
                >
                  🚀 Generate Masterpiece
                </button>
              </div>
            </div>
          )}

        </div>
      )}

      {/* ── STEP 3: FORGE (Running State) ───────────────────── */}
      {isRunning && (
        <div className="section-card forge-step">
          <div className="step-indicator">
            <div className="step-dot completed"></div>
            <div className="step-dot completed"></div>
            <div className="step-dot active"></div>
            <div className="step-dot"></div>
          </div>
          
          <div className="section-title">
            <span className="section-title-icon">🏗️</span>
            Step 3: Forging Your Masterpiece
          </div>

          <div className="progress-area">
            <div className="progress-header">
              <span className="progress-title">
                {completedCount === STEPS.length ? "Finalizing…" : `Agent Phase ${Math.min(completedCount + 1, STEPS.length)} of ${STEPS.length}`}
              </span>
              <span className="progress-pct">{progress}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          <div className="step-list">
            {steps.map(s => (
              <StepRow key={s.id} icon={s.icon} label={s.label} status={s.status} />
            ))}
          </div>

          <button className="btn-new" onClick={handleReset} style={{ alignSelf: 'center' }}>Cancel Forge</button>
        </div>
      )}

      {/* ── STEP 4: EXPORT (Done State) ──────────────────────── */}
      {isDone && (
        <div className="section-card export-step">
          <div className="step-indicator">
            <div className="step-dot completed"></div>
            <div className="step-dot completed"></div>
            <div className="step-dot completed"></div>
            <div className="step-dot active"></div>
          </div>

          <div className="section-title">
            <span className="section-title-icon">✅</span>
            Step 4: Export & Finalize
          </div>

          <div className="success-card" style={{ border: 'none', background: 'transparent', padding: 0 }}>
            <div className="success-icon float">🎬</div>
            <div>
              <div className="success-title">Your video is ready!</div>
              <div className="success-sub" style={{ marginTop: "8px" }}>
                {finalData?.title || "Your AI-generated video has been created successfully."}
              </div>
            </div>

            <div className="video-meta">
              <div className="meta-pill">🎬 <span>{finalData?.scene_count || 0}</span> scenes</div>
              <div className="meta-pill">⏱ <span>{fmtDur(finalData?.estimated_duration_seconds)}</span></div>
              <div className="meta-pill">🔍 SEO <span>{finalData?.seo_score || 85}</span>/100</div>
            </div>

            <div style={{ display: 'flex', gap: '16px', marginTop: '24px' }}>
              <button className="btn-generate" style={{ flex: 1 }} onClick={handleDownload}>⬇️ Download MP4</button>
              <button className="btn-new" onClick={handleReset}>+ New Project</button>
            </div>
          </div>
        </div>
      )}

      {/* ── ERROR state ─────────────────────────────────────── */}
      {isError && (
        <div style={{ width: "100%", marginTop: "24px" }}>
          <div className="error-card">
            <div className="error-title">⚠️ Something went wrong</div>
            <div className="error-msg">{errorMsg}</div>
            <button className="btn-retry" onClick={handleReset}>
              ↩ Try Again
            </button>
          </div>
        </div>
      )}
      </>
      )}

      {/* ── MY VIDEOS VIEW ──────────────────────────────────── */}
      {activeView === "videos" && (
        <div className="workspace-section" style={{ marginTop: 0 }}>
          <div className="workspace-header">
            <h2 className="workspace-title">Your Video Library</h2>
            <div className="workspace-label">WORKSPACE / MY VIDEOS</div>
          </div>
          
          <div className="project-grid">
            {isLoading ? (
              <div style={{ color: 'var(--text-dim)', padding: '40px' }}>Loading your masterpieces...</div>
            ) : projects.length > 0 ? (
              projects.map(proj => (
                <div key={proj.id} className="project-card">
                  <div className="project-thumb" style={{ background: 'var(--grad-main)', opacity: 0.8 }}>
                    <div className="thumb-overlay">
                      <button className="btn-play" onClick={() => handleDownload(proj.id)}>⬇️</button>
                    </div>
                  </div>
                  <div className="project-info">
                    <div className="project-title">{proj.topic}</div>
                    <div className="project-meta">
                      <span>{proj.scene_count} scenes</span> • <span>SEO {proj.seo_score}</span>
                    </div>
                    <div className="project-date">{proj.created_at}</div>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ color: 'var(--text-dim)', padding: '40px' }}>No videos generated yet. Start one in the Generator!</div>
            )}
          </div>
        </div>
      )}

      {/* ── ANALYTICS VIEW ──────────────────────────────────── */}
      {activeView === "analytics" && (
        <div className="workspace-section" style={{ marginTop: 0 }}>
          <div className="workspace-header">
            <h2 className="workspace-title">Performance Analytics</h2>
            <div className="workspace-label">WORKSPACE / ANALYTICS</div>
          </div>
          
          <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
            <div className="section-card" style={{ textAlign: 'center' }}>
              <div className="field-label">Total Videos</div>
              <div className="success-title" style={{ fontSize: '3rem' }}>{stats.total_videos}</div>
            </div>
            <div className="section-card" style={{ textAlign: 'center' }}>
              <div className="field-label">Avg. Retention</div>
              <div className="success-title" style={{ fontSize: '3rem', color: 'var(--accent-glow)' }}>{stats.avg_retention}</div>
            </div>
            <div className="section-card" style={{ textAlign: 'center' }}>
              <div className="field-label">SEO Performance</div>
              <div className="success-title" style={{ fontSize: '3rem', color: 'var(--accent-cool)' }}>{stats.avg_seo}</div>
            </div>
          </div>
          
          <div className="section-card" style={{ marginTop: '20px' }}>
            <div className="section-title">📈 SEO Trend (Last 7 Videos)</div>
            <div style={{ height: '200px', width: '100%', background: 'var(--bg-glass)', borderRadius: '12px', display: 'flex', alignItems: 'flex-end', gap: '8px', padding: '20px' }}>
              {stats.history.length > 0 ? stats.history.map((h, i) => (
                <div key={i} style={{ flex: 1, height: `${h}%`, background: 'var(--grad-main)', borderRadius: '4px 4px 0 0', opacity: 0.7, transition: 'height 1s ease' }} />
              )) : (
                <div style={{ color: 'var(--text-dim)', margin: 'auto' }}>No data available yet.</div>
              )}
            </div>
          </div>
        </div>
      )}

      </div>

      {/* ── API Settings Modal ─────────────────────────── */}
      {isSettingsOpen && (
        <div className="modal-overlay" onClick={() => setIsSettingsOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">🔑 API Configuration</h2>
              <button className="btn-close" onClick={() => setIsSettingsOpen(false)}>×</button>
            </div>

            <p style={{ color: "var(--text-2)", fontSize: "14px", marginBottom: "10px" }}>
              Enter your own API keys below. They will be <strong>stored with AES-256 encryption</strong>.
            </p>

            <div className="settings-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '20px' }}>
              {[
                { id: "gemini_api", label: "Gemini API Key", provider: "gemini" },
                { id: "groq_api", label: "Groq API Key", provider: "groq" },
                { id: "pexels_api", label: "Pexels API Key", provider: "pexels" },
                { id: "pixabay_api", label: "Pixabay API Key", provider: "pixabay" },
                { id: "elevenlabs_api", label: "ElevenLabs API Key", provider: "elevenlabs" },
                { id: "unreal_speech_api", label: "Unreal Speech API Key", provider: "unreal" },
              ].map(field => (
                <div key={field.id}>
                  <div className="field-label">{field.label}</div>
                  <div className="key-input-row" style={{ display: 'flex', gap: '8px' }}>
                    <input 
                      type="password"
                      className="topic-input"
                      style={{ padding: "10px 14px", fontSize: "14px" }}
                      placeholder={userKeys[field.id] ? "••••••••••••" : "Paste key..."}
                      value={userKeys[field.id].includes("...") ? "" : userKeys[field.id]}
                      onChange={e => setUserKeys(prev => ({ ...prev, [field.id]: e.target.value }))}
                    />
                    <button 
                      className={`chip ${verifyStatus[field.provider] || ''}`}
                      style={{ padding: '0 12px', fontSize: '12px' }}
                      onClick={() => handleVerifyKey(field.provider, userKeys[field.id])}
                      disabled={verifyStatus[field.provider] === 'verifying' || !userKeys[field.id]}
                    >
                      {verifyStatus[field.provider] === 'verifying' ? '⏳' : 
                       verifyStatus[field.provider] === 'success' ? '✅' : 
                       verifyStatus[field.provider] === 'failed' ? '❌' : 'Verify'}
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <button className="btn-generate" style={{ marginTop: '24px', width: '100%' }} onClick={handleSaveSettings}>
              🔒 Encrypt & Save All Keys
            </button>
          </div>
        </div>
      )}
    </Layout>
  );
}
