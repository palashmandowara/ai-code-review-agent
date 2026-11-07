import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  Check,
  ChevronRight,
  Code2,
  FileCode2,
  FlaskConical,
  GitPullRequest,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  Plus,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import "./style.css";

type Finding = {
  file_path: string;
  line_start: number;
  title: string;
  severity: string;
  explanation: string;
  evidence: string;
  suggested_fix?: string;
};
type Run = {
  id: string;
  title: string;
  source: string;
  status: string;
  approach: string;
  created_at: string;
  duration_ms: number | null;
  finding_count?: number;
  findings?: Finding[];
  diff?: string;
  error?: string;
  url?: string;
  metadata: Record<string, unknown>;
};
const example =
  "diff --git a/access.py b/access.py\n--- a/access.py\n+++ b/access.py\n@@ -1,2 +1,2 @@\n def can_delete(actor, owner):\n-    return actor.id == owner.id\n+    return True\n";
const labels: Record<string, string> = {
  plain: "Plain prompt",
  context: "Repository context",
  tool: "Tool-assisted",
};
function App() {
  const [page, setPage] = useState("overview"),
    [token, setToken] = useState(""),
    [draftToken, setDraftToken] = useState(""),
    [runs, setRuns] = useState<Run[]>([]),
    [selected, setSelected] = useState<Run | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [query, setQuery] = useState(""),
    [status, setStatus] = useState("all");
  const [title, setTitle] = useState(""),
    [diff, setDiff] = useState(""),
    [approach, setApproach] = useState("plain"),
    [context, setContext] = useState(""),
    [submitting, setSubmitting] = useState(false);
  async function api(path: string, options: RequestInit = {}) {
    const response = await fetch("/api/dashboard" + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...options.headers,
      },
    });
    const body = await response.json();
    if (!response.ok)
      throw new Error(
        typeof body.detail === "string"
          ? body.detail
          : "Check the submitted fields and try again.",
      );
    return body;
  }
  async function refresh() {
    setLoading(true);
    setError("");
    try {
      setRuns(await api("/runs"));
    } catch (e) {
      setError((e as Error).message);
      setToken("");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (token) {
      void refresh();
      const id = setInterval(() => {
        void refresh();
      }, 15000);
      return () => clearInterval(id);
    }
  }, [token]);
  useEffect(() => {
    if (
      !token ||
      page !== "detail" ||
      !selected ||
      !["queued", "running"].includes(selected.status)
    )
      return;
    let stopped = false;
    const timer = setInterval(async () => {
      try {
        const fresh = await api("/runs/" + selected.id);
        if (!stopped) setSelected(fresh);
      } catch (e) {
        if (!stopped) setError((e as Error).message);
      }
    }, 2000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [token, page, selected?.id, selected?.status]);
  async function retrySelected() {
    if (!selected) return;
    try {
      setSelected(
        await api("/runs/" + selected.id + "/retry", { method: "POST" }),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function open(id: string) {
    setError("");
    try {
      setSelected(await api("/runs/" + id));
      setPage("detail");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const run = await api("/reviews", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim() || "Manual review",
          diff,
          approach,
          context,
        }),
      });
      setSelected(run);
      setPage("detail");
      void refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  const completed = runs.filter((r) => r.status === "completed"),
    findings = runs.reduce((a, r) => a + (r.finding_count || 0), 0),
    visible = runs.filter(
      (r) =>
        r.title.toLowerCase().includes(query.toLowerCase()) &&
        (status === "all" || r.status === status),
    );
  function navigate(p: string) {
    setPage(p);
    setError("");
  }
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="#" onClick={() => navigate("overview")}>
          <span className="brand-icon">
            <Code2 size={23} />
          </span>
          review<span className="brand-light">agent</span>
          <span className="version">BETA</span>
        </a>
        <div className="workspace">
          <div className="workspace-avatar">W</div>
          <div>
            My workspace<small>Developer tools</small>
          </div>
          <ChevronRight size={15} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          <button
            className={page === "overview" || page === "detail" ? "active" : ""}
            onClick={() => navigate("overview")}
          >
            <LayoutDashboard size={18} />
            Overview
          </button>
          <button
            className={page === "new" ? "active" : ""}
            onClick={() => navigate("new")}
          >
            <GitPullRequest size={18} />
            New review
          </button>
          <button
            className={page === "benchmark" ? "active" : ""}
            onClick={() => navigate("benchmark")}
          >
            <FlaskConical size={18} />
            Benchmarks<span className="tiny">PILOT</span>
          </button>
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={20} />
          <strong>Evidence over noise.</strong>
          <p>
            Review changed code.
            <br />
            Keep the findings that matter.
          </p>
        </div>
        <button
          className="connection"
          onClick={() => {
            setToken("");
            setRuns([]);
            setSelected(null);
          }}
        >
          <span className={"dot " + (token ? "green" : "")} />
          {token ? "Connected · Disconnect" : "Local workspace"}
          <LockKeyhole size={14} />
        </button>
      </aside>
      <main>
        <header>
          <span>
            Workspace <ChevronRight size={13} />{" "}
            {page === "benchmark"
              ? "Benchmarks"
              : page === "new"
                ? "New review"
                : page === "detail"
                  ? "Review details"
                  : "Overview"}
          </span>
          <div className="header-right">
            <span className="outlined">
              <span className="dot green" />{" "}
              {token ? "API connected" : "Private dashboard"}
            </span>
            {token && (
              <button
                className="text-button"
                onClick={() => {
                  setToken("");
                  setRuns([]);
                  setSelected(null);
                }}
              >
                Disconnect
              </button>
            )}
            <div className="avatar">You</div>
          </div>
        </header>
        <div className="content">
          <div className="eyebrow">
            AI CODE REVIEW / {page === "benchmark" ? "EVALUATION" : "WORKSPACE"}
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {!token ? (
            <section className="connect">
              <div className="connect-icon">
                <LockKeyhole size={28} />
              </div>
              <h1>Your code. A clearer review.</h1>
              <p>
                Connect to your review service to inspect findings,
                <br />
                follow pull requests, and compare approaches.
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setToken(draftToken);
                  setDraftToken("");
                }}
              >
                <label htmlFor="token">Dashboard access token</label>
                <input
                  id="token"
                  type="password"
                  required
                  value={draftToken}
                  onChange={(e) => setDraftToken(e.target.value)}
                  placeholder="Enter your DASHBOARD_TOKEN"
                />
                <button className="primary">
                  Connect workspace <ArrowUpRight size={16} />
                </button>
              </form>
              <small>
                Your token stays in memory and clears when you close or reload
                this page.
              </small>
            </section>
          ) : (
            <>
              {page === "overview" && (
                <>
                  <div className="page-heading">
                    <div>
                      <h1>
                        Review overview<span className="heading-dot">.</span>
                      </h1>
                      <p>
                        A little context. A lot more confidence in your code.
                      </p>
                    </div>
                    <button className="primary" onClick={() => navigate("new")}>
                      <Plus size={16} />
                      New review
                    </button>
                  </div>
                  <div className="stats">
                    {[
                      [
                        GitPullRequest,
                        "Review runs",
                        runs.length,
                        "Most recent 100 runs",
                      ],
                      [
                        ShieldCheck,
                        "Completed",
                        completed.length,
                        "Reviews ready to inspect",
                      ],
                      [
                        Code2,
                        "Findings",
                        findings,
                        "Validated review comments",
                      ],
                      [
                        Activity,
                        "In progress",
                        runs.filter((r) =>
                          ["queued", "running"].includes(r.status),
                        ).length,
                        "Updates every 15 seconds",
                      ],
                    ].map(([Icon, label, value, note]) => {
                      const I = Icon as typeof Activity;
                      return (
                        <section className="stat" key={String(label)}>
                          <div>
                            <span>{String(label)}</span>
                            <I size={17} />
                          </div>
                          <strong>{String(value).padStart(2, "0")}</strong>
                          <small>{String(note)}</small>
                        </section>
                      );
                    })}
                  </div>
                  <section className="panel">
                    <div className="panel-head">
                      <div>
                        <h2>
                          Recent reviews{" "}
                          <span className="count">{runs.length}</span>
                        </h2>
                        <p>From pull request to actionable feedback.</p>
                      </div>
                      <button
                        className="text-button"
                        onClick={() => void refresh()}
                        disabled={loading}
                      >
                        {loading ? "Refreshing…" : "Refresh"}{" "}
                        <Activity size={14} />
                      </button>
                    </div>
                    <div className="filters">
                      <label className="search">
                        <Search size={16} />
                        <input
                          aria-label="Search reviews"
                          placeholder="Search reviews…"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                      </label>
                      <select
                        aria-label="Filter status"
                        value={status}
                        onChange={(e) => setStatus(e.target.value)}
                      >
                        <option value="all">All statuses</option>
                        {[
                          "completed",
                          "running",
                          "queued",
                          "failed",
                          "stale",
                          "skipped",
                        ].map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>REVIEW</th>
                            <th>APPROACH</th>
                            <th>STATUS</th>
                            <th>FINDINGS</th>
                            <th>CREATED</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {visible.map((r) => (
                            <tr key={r.id}>
                              <td>
                                <button
                                  className="review-link"
                                  onClick={() => void open(r.id)}
                                >
                                  <span className="file-icon">
                                    <GitPullRequest size={18} />
                                  </span>
                                  <span>
                                    {r.title}
                                    <small>
                                      {r.source === "github"
                                        ? "GitHub pull request"
                                        : "Manual diff review"}
                                    </small>
                                  </span>
                                </button>
                              </td>
                              <td>{labels[r.approach] || r.approach}</td>
                              <td>
                                <span className={"badge " + r.status}>
                                  {r.status === "completed" && (
                                    <Check size={12} />
                                  )}{" "}
                                  {r.status}
                                </span>
                              </td>
                              <td>
                                <span className="finding-number">
                                  {r.finding_count || 0}
                                </span>
                              </td>
                              <td className="muted">
                                {new Date(r.created_at).toLocaleDateString(
                                  undefined,
                                  { month: "short", day: "numeric" },
                                )}
                              </td>
                              <td>
                                <button
                                  aria-label={"Open " + r.title}
                                  className="icon-button"
                                  onClick={() => void open(r.id)}
                                >
                                  <ArrowUpRight size={16} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {!visible.length && (
                      <div className="empty">
                        <GitPullRequest size={30} />
                        <h3>
                          {runs.length
                            ? "No matching reviews"
                            : "Your first review starts here"}
                        </h3>
                        <p>
                          {runs.length
                            ? "Try a different search or status."
                            : "Open a pull request on your connected repository, or review a diff below."}
                        </p>
                        {!runs.length && (
                          <button
                            className="secondary"
                            onClick={() => navigate("new")}
                          >
                            Review a diff <ChevronRight size={15} />
                          </button>
                        )}
                      </div>
                    )}
                  </section>
                  <div className="bottom-grid">
                    <section className="feature-card">
                      <div className="feature-icon">
                        <Code2 size={22} />
                      </div>
                      <div>
                        <h3>Three ways to see the code.</h3>
                        <p>
                          Plain prompting, repository context, and static
                          analysis.
                          <br />
                          One pipeline, different perspectives.
                        </p>
                      </div>
                    </section>
                    <button
                      className="pilot-card"
                      onClick={() => navigate("benchmark")}
                    >
                      <div>
                        <span className="eyebrow">THE EXPERIMENT</span>
                        <h3>Explore the six-case pilot</h3>
                        <p>Small sample. Transparent limitations.</p>
                      </div>
                      <ArrowUpRight size={22} />
                    </button>
                  </div>
                </>
              )}
              {page === "new" && (
                <>
                  <div className="page-heading">
                    <div>
                      <h1>
                        A fresh pair of eyes
                        <span className="heading-dot">.</span>
                      </h1>
                      <p>
                        Submit a unified diff. Get findings grounded in changed
                        lines.
                      </p>
                    </div>
                  </div>
                  <form onSubmit={submit} className="review-form panel">
                    <div className="form-main">
                      <label htmlFor="title">Review name</label>
                      <input
                        id="title"
                        maxLength={120}
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="e.g. Fix account permissions"
                      />
                      <div className="field-heading">
                        <label htmlFor="diff">Unified diff</label>
                        <button
                          type="button"
                          className="text-button"
                          onClick={() => setDiff(example)}
                        >
                          Load example <ArrowDownLeft size={14} />
                        </button>
                      </div>
                      <textarea
                        id="diff"
                        className="code-input"
                        required
                        maxLength={30000}
                        value={diff}
                        onChange={(e) => setDiff(e.target.value)}
                        placeholder={
                          "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old code\n+new code"
                        }
                      />
                      <div className="field-foot">
                        <label className="upload">
                          Upload .diff / .patch
                          <input
                            type="file"
                            accept=".diff,.patch,.txt"
                            onChange={async (e) => {
                              const f = e.target.files?.[0];
                              if (f) {
                                if (f.size > 30000) {
                                  setError(
                                    "Diff must be at most 30,000 bytes.",
                                  );
                                  return;
                                }
                                setDiff(await f.text());
                              }
                            }}
                          />
                        </label>
                        <small>
                          {diff.length.toLocaleString()} / 30,000 characters
                        </small>
                      </div>
                      {approach === "context" && (
                        <>
                          <label htmlFor="context">Repository context</label>
                          <textarea
                            id="context"
                            required
                            maxLength={12000}
                            value={context}
                            onChange={(e) => setContext(e.target.value)}
                            placeholder="Paste relevant definitions, callers, tests, or contracts…"
                          />
                        </>
                      )}
                    </div>
                    <div className="form-side">
                      <h3>Review approach</h3>
                      {["plain", "context"].map((a) => (
                        <label
                          className={
                            "approach " + (approach === a ? "chosen" : "")
                          }
                          key={a}
                        >
                          <input
                            type="radio"
                            name="approach"
                            checked={approach === a}
                            onChange={() => setApproach(a)}
                          />
                          <div>
                            <strong>{labels[a]}</strong>
                            <p>
                              {a === "plain"
                                ? "Review the changed code on its own."
                                : "Include the source context you provide."}
                            </p>
                          </div>
                        </label>
                      ))}
                      <p className="helper">
                        Tool-assisted reviews run through the GitHub App or
                        benchmark CLI, where source files are available to Ruff.
                      </p>
                      <div className="notice">
                        <ShieldCheck size={18} />
                        <p>
                          This sends code to your configured model provider.
                          Findings stay in this dashboard; nothing is posted to
                          GitHub.
                        </p>
                      </div>
                      <button className="primary full" disabled={submitting}>
                        {submitting ? (
                          <>
                            <LoaderCircle className="spin" size={16} />
                            Reviewing…
                          </>
                        ) : (
                          <>
                            Run review
                            <ArrowUpRight size={16} />
                          </>
                        )}
                      </button>
                      {submitting && (
                        <small role="status">
                          Your review is saved to the queue and continues in the
                          background.
                        </small>
                      )}
                    </div>
                  </form>
                </>
              )}
              {page === "detail" && selected && (
                <>
                  <button
                    className="text-button back"
                    onClick={() => navigate("overview")}
                  >
                    ← All reviews
                  </button>
                  <div className="page-heading">
                    <div>
                      <h1 className="detail-title">{selected.title}</h1>
                      <p>
                        {labels[selected.approach]} ·{" "}
                        {new Date(selected.created_at).toLocaleString()}{" "}
                        {selected.duration_ms != null &&
                          `· ${(selected.duration_ms / 1000).toFixed(1)}s`}
                      </p>
                    </div>
                    <span className={"badge " + selected.status}>
                      {selected.status}
                    </span>
                  </div>
                  {selected.error && (
                    <div className="error" role="alert">
                      {selected.error}
                      {selected.status === "failed" && (
                        <button
                          className="secondary"
                          onClick={() => void retrySelected()}
                        >
                          Retry review
                        </button>
                      )}
                    </div>
                  )}
                  <div className="detail-grid">
                    <section className="panel diff-panel">
                      <div className="panel-head">
                        <h2>
                          <FileCode2 size={17} /> Changed code
                        </h2>
                        {selected.url && (
                          <a
                            href={selected.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-button"
                          >
                            View PR <ArrowUpRight size={14} />
                          </a>
                        )}
                      </div>
                      {selected.diff ? (
                        <pre className="diff">
                          {selected.diff.split("\n").map((line, i) => (
                            <div
                              key={i}
                              className={
                                line.startsWith("+")
                                  ? "added"
                                  : line.startsWith("-")
                                    ? "removed"
                                    : line.startsWith("@@")
                                      ? "hunk"
                                      : ""
                              }
                            >
                              <span className="line-number">{i + 1}</span>
                              {line || " "}
                            </div>
                          ))}
                        </pre>
                      ) : (
                        <div className="empty">
                          <FileCode2 size={28} />
                          <h3>Source stays in GitHub</h3>
                          <p>
                            Historical GitHub runs store findings, not the
                            original diff.
                            <br />
                            Open the pull request to inspect changed code.
                          </p>
                        </div>
                      )}
                    </section>
                    <section className="findings">
                      <h2>
                        Findings{" "}
                        <span className="count">
                          {selected.findings?.length || 0}
                        </span>
                      </h2>
                      {selected.metadata.model === "offline-demo-rule" && (
                        <div className="notice">
                          Demo rule output · not an AI review
                        </div>
                      )}
                      {selected.findings?.map((f, i) => (
                        <article className="finding" key={i}>
                          <div className="finding-top">
                            <span
                              className={
                                "badge severity " + f.severity.toLowerCase()
                              }
                            >
                              {f.severity}
                            </span>
                            <span>#{i + 1}</span>
                          </div>
                          <h3>{f.title}</h3>
                          <code>
                            {f.file_path}:{f.line_start}
                          </code>
                          <p>{f.explanation}</p>
                          <details>
                            <summary>Supporting evidence</summary>
                            <pre>{f.evidence}</pre>
                            {f.suggested_fix && (
                              <>
                                <strong>Suggested fix</strong>
                                <pre>{f.suggested_fix}</pre>
                              </>
                            )}
                          </details>
                        </article>
                      ))}
                      {!selected.findings?.length && (
                        <div className="panel empty">
                          <ShieldCheck size={28} />
                          <h3>
                            {selected.status === "completed"
                              ? "No findings reported"
                              : "No findings available"}
                          </h3>
                          <p>
                            {selected.status === "completed"
                              ? "An empty review does not guarantee the code is bug-free."
                              : "Findings appear after a successful review."}
                          </p>
                        </div>
                      )}
                    </section>
                  </div>
                </>
              )}
              {page === "benchmark" && (
                <>
                  <div className="page-heading">
                    <div>
                      <h1>
                        Measure, then improve
                        <span className="heading-dot">.</span>
                      </h1>
                      <p>
                        Published pilot · October 17, 2026 · Groq / GPT-OSS 20B
                        · Prompt v2
                      </p>
                    </div>
                    <span className="outlined">6 cases · 3 approaches</span>
                  </div>
                  <div className="benchmark-notice">
                    <FlaskConical size={23} />
                    <div>
                      <strong>
                        A workflow check, not a general accuracy claim.
                      </strong>
                      <p>
                        Four adapted BugsInPy regressions and two synthetic
                        clean controls. One run per approach. Context was
                        reconstructed; this was not a held-out experiment.
                      </p>
                    </div>
                  </div>
                  <div className="benchmark-grid">
                    {[
                      {
                        key: "plain",
                        found: 4,
                        rejected: 0,
                        latency: "1.25",
                        precision: "1.00",
                      },
                      {
                        key: "context",
                        found: 3,
                        rejected: 1,
                        latency: "1.03",
                        precision: "0.75",
                      },
                      {
                        key: "tool",
                        found: 4,
                        rejected: 0,
                        latency: "1.03",
                        precision: "1.00",
                      },
                    ].map((b, i) => (
                      <section className="panel benchmark-card" key={b.key}>
                        <span className="eyebrow">APPROACH 0{i + 1}</span>
                        <h2>{labels[b.key]}</h2>
                        <div className="score">
                          {b.found}
                          <span>/ 4</span>
                        </div>
                        <p>intended bugs found</p>
                        <div className="bar">
                          <span style={{ width: `${b.found * 25}%` }} />
                        </div>
                        <dl>
                          <div>
                            <dt>Rejected findings</dt>
                            <dd>{b.rejected}</dd>
                          </div>
                          <div>
                            <dt>Clean controls with comments</dt>
                            <dd>0 / 2</dd>
                          </div>
                          <div>
                            <dt>Location precision / recall / F1</dt>
                            <dd>{b.precision}</dd>
                          </div>
                          <div>
                            <dt>Median latency</dt>
                            <dd>{b.latency}s</dd>
                          </div>
                        </dl>
                      </section>
                    ))}
                  </div>
                  <section className="panel interpretation">
                    <h2>Read the results with context</h2>
                    <p>
                      The context approach selected an unchanged line for one
                      bug, resulting in one rejected finding and one missed
                      defect. Plain and tool-assisted tied on this small sample;
                      this does not establish that tools improve accuracy.
                    </p>
                    <p>
                      Location matching needs semantic review. Token prices were
                      not configured, so the recorded $0 estimate is not a
                      measured cost. Raw model outputs are not published in the
                      repository.
                    </p>
                    <a
                      className="text-button"
                      target="_blank"
                      rel="noreferrer"
                      href="https://github.com/palashmandowara/ai-code-review-agent/blob/main/docs/pilot-results.md"
                    >
                      Read the source report <ArrowUpRight size={15} />
                    </a>
                  </section>
                </>
              )}
            </>
          )}
          <footer>
            <span>
              <Code2 size={14} /> Built for thoughtful code reviews.
            </span>
            <span>
              Review Agent <span className="muted">/ v0.1</span>
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
