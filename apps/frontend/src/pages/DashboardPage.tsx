import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { getSavedUserId, logout } from "../api/auth";
import { fetchUserHistory, type HistoryItem } from "../types/history";
import {
  fetchHybridRecommendations,
  fetchPreferenceRecommendations,
  type RecommendationItem,
  type ParsedPreferences,
} from "../types/recommend";

import { logInteractionEvent } from "../api/events";

const POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500";
const POSTER_HERO_URL = "https://image.tmdb.org/t/p/original";

type TabKey = "history" | "hybrid" | "preferences";

export default function DashboardPage() {
  const navigate = useNavigate();

  const [userId, setUserId] = useState<number | null>(null);

  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [hybridRecommendations, setHybridRecommendations] = useState<RecommendationItem[]>([]);
  const [preferenceRecommendations, setPreferenceRecommendations] = useState<RecommendationItem[]>([]);

  const [activeTab, setActiveTab] = useState<TabKey>("hybrid");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [preferenceText, setPreferenceText] = useState("");
  const [parsedPrefs, setParsedPrefs] = useState<ParsedPreferences | null>(null);
  const [isRefining, setIsRefining] = useState(false);
  const [refineError, setRefineError] = useState<string | null>(null);

  useEffect(() => {
    const savedUserId = getSavedUserId();

    if (!savedUserId) {
      navigate("/");
      return;
    }

    setUserId(Number(savedUserId));
  }, [navigate]);

  useEffect(() => {
    async function loadData() {
      if (!userId) return;

      try {
        setLoading(true);
        setError(null);

        const [historyRes, hybridRes] = await Promise.all([
          fetchUserHistory(userId, 20),
          fetchHybridRecommendations(userId, 10),
        ]);

        setHistory(historyRes.history || []);
        setHybridRecommendations(hybridRes.recommendations || []);
      } catch (err) {
        console.error(err);
        setError("Failed to load dashboard data.");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [userId]);

  function handleLogout() {
    logout();
    navigate("/");
  }

  async function handlePreferenceSearch() {
    if (!userId) return;

    const trimmed = preferenceText.trim();
    if (!trimmed) {
      setRefineError("Please enter a preference.");
      return;
    }

    try {
      setIsRefining(true);
      setRefineError(null);

      const res = await fetchPreferenceRecommendations({
        user_id: userId,
        preference_text: trimmed,
        limit: 10,
      });

      setPreferenceRecommendations(res.recommendations || []);
      setParsedPrefs(res.parsed_preferences || null);
      setActiveTab("preferences");
    } catch (err) {
      console.error(err);
      setRefineError("Failed to refine recommendations.");
    } finally {
      setIsRefining(false);
    }
  }

  async function handleResetHybrid() {
    if (!userId) return;

    try {
      setIsRefining(true);
      setRefineError(null);

      const res = await fetchHybridRecommendations(userId, 10);
      setHybridRecommendations(res.recommendations || []);
      setPreferenceRecommendations([]);
      setParsedPrefs(null);
      setPreferenceText("");
      setActiveTab("hybrid");
    } catch (err) {
      console.error(err);
      setRefineError("Failed to reload hybrid recommendations.");
    } finally {
      setIsRefining(false);
    }
  }

  async function refreshHybridRecommendations() {
    if (!userId) return;

    try {
      const res = await fetchHybridRecommendations(userId, 10);
      setHybridRecommendations(res.recommendations || []);
    } catch (err) {
      console.error("Failed to refresh hybrid recommendations:", err);
    }
  }

  // Top hybrid recommendation drives the hero banner.
  const featured = useMemo(
    () => hybridRecommendations[0] ?? null,
    [hybridRecommendations],
  );

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 text-neutral-300">
        <div className="flex flex-col items-center gap-4">
          <div className="h-12 w-12 animate-spin rounded-full border-2 border-neutral-800 border-t-red-500" />
          <p className="text-sm tracking-wide text-neutral-400">Loading your movies…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      {/* Sticky top nav */}
      <header className="sticky top-0 z-30 border-b border-neutral-900/80 bg-neutral-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-red-500 to-amber-500 font-black text-neutral-950">
              M
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">MovieReco</h1>
              <p className="text-xs text-neutral-500">Profile #{userId}</p>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="rounded-full border border-neutral-800 px-4 py-1.5 text-sm text-neutral-300 transition hover:border-neutral-700 hover:bg-neutral-900"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Featured hero */}
      {featured && (
        <Hero
          movie={featured}
          userId={userId!}
          onInteraction={refreshHybridRecommendations}
        />
      )}

      <main className="mx-auto max-w-7xl px-6 pb-20">
        {error && (
          <div className="mb-6 rounded-2xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Refine search */}
        <section className="-mt-12 mb-10 rounded-3xl border border-neutral-800 bg-gradient-to-br from-neutral-900 to-neutral-950 p-6 shadow-2xl shadow-black/50">
          <div className="mb-3 flex items-center gap-2">
            <SparkleIcon className="h-4 w-4 text-amber-400" />
            <h2 className="text-xs font-semibold uppercase tracking-widest text-neutral-300">
              Refine with natural language
            </h2>
          </div>

          <div className="flex flex-col gap-3 md:flex-row">
            <input
              value={preferenceText}
              onChange={(e) => setPreferenceText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handlePreferenceSearch();
              }}
              placeholder='e.g. "dark psychological thriller, no sci-fi, like Fincher"'
              className="flex-1 rounded-xl border border-neutral-800 bg-neutral-950/60 px-4 py-3 text-neutral-100 placeholder-neutral-600 transition focus:border-red-500/60 focus:outline-none focus:ring-2 focus:ring-red-500/20"
            />

            <button
              onClick={handlePreferenceSearch}
              disabled={isRefining}
              className="rounded-xl bg-red-600 px-5 py-3 font-medium text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isRefining ? "Refining…" : "Refine"}
            </button>

            <button
              onClick={handleResetHybrid}
              className="rounded-xl border border-neutral-800 px-5 py-3 text-sm text-neutral-300 transition hover:border-neutral-700 hover:bg-neutral-900"
            >
              Reset
            </button>
          </div>

          {refineError && (
            <div className="mt-4 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
              {refineError}
            </div>
          )}

          {parsedPrefs && (
            <div className="mt-5">
              <p className="mb-2 text-xs uppercase tracking-wider text-neutral-500">
                Detected
              </p>

              <div className="flex flex-wrap gap-2">
                {parsedPrefs.include_genres?.map((g) => (
                  <Chip key={`include-${g}`} variant="include">{g}</Chip>
                ))}

                {parsedPrefs.exclude_genres?.map((g) => (
                  <Chip key={`exclude-${g}`} variant="exclude">No {g}</Chip>
                ))}

                {parsedPrefs.preferred_directors?.map((d) => (
                  <Chip key={`director-${d}`} variant="director">{d}</Chip>
                ))}

                {parsedPrefs.tone?.map((t) => (
                  <Chip key={`tone-${t}`} variant="tone">{t}</Chip>
                ))}

                {parsedPrefs.keywords?.map((k) => (
                  <Chip key={`keyword-${k}`} variant="neutral">{k}</Chip>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Tabs */}
        <nav className="mb-8 flex w-fit gap-1 rounded-full border border-neutral-800 bg-neutral-900/50 p-1">
          <TabButton active={activeTab === "hybrid"} onClick={() => setActiveTab("hybrid")}>
            For You
          </TabButton>
          <TabButton active={activeTab === "preferences"} onClick={() => setActiveTab("preferences")}>
            Refined
          </TabButton>
          <TabButton active={activeTab === "history"} onClick={() => setActiveTab("history")}>
            History
          </TabButton>
        </nav>

        {/* Content */}
        {activeTab === "history" && (
          <Section
            title="Watch History"
            subtitle="Movies you've liked recently."
          >
            {history.length === 0 ? (
              <EmptyState message="No history found yet." />
            ) : (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
                {history.map((movie) => (
                  <HistoryCard
                    key={`${movie.movieId}-${movie.timestamp ?? "na"}`}
                    movie={movie}
                  />
                ))}
              </div>
            )}
          </Section>
        )}

        {activeTab === "hybrid" && (
          <Section
            title="Recommended For You"
            subtitle="Personalized picks from the hybrid model."
          >
            {hybridRecommendations.length === 0 ? (
              <EmptyState message="No recommendations available." />
            ) : (
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {hybridRecommendations.map((movie) => (
                  <RecommendationCard
                    key={`hybrid-${movie.movieId}`}
                    movie={movie}
                    userId={userId!}
                    source="hybrid_recommendations"
                    onInteraction={refreshHybridRecommendations}
                  />
                ))}
              </div>
            )}
          </Section>
        )}

        {activeTab === "preferences" && (
          <Section
            title="Refined Picks"
            subtitle="Tailored to your free-text preferences."
          >
            {preferenceRecommendations.length === 0 ? (
              <EmptyState message="Use the refine box above to get tailored picks." />
            ) : (
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {preferenceRecommendations.map((movie) => (
                  <RecommendationCard
                    key={`pref-${movie.movieId}`}
                    movie={movie}
                    userId={userId!}
                    source="preference_recommendations"
                    onInteraction={refreshHybridRecommendations}
                  />
                ))}
              </div>
            )}
          </Section>
        )}
      </main>
    </div>
  );
}

/* ----------------------------- Subcomponents ----------------------------- */

function Hero({
  movie,
  userId,
  onInteraction,
}: {
  movie: RecommendationItem;
  userId: number;
  onInteraction?: () => void;
}) {
  async function handleClick() {
    try {
      await logInteractionEvent({
        user_id: userId,
        movie_id: movie.movieId,
        event_type: "movie_click",
        event_value: 1.0,
        source: "hero",
        rank: movie.rank,
        metadata: { title: movie.title, source: "hero" },
      });
      onInteraction?.();
    } catch (err) {
      console.error(err);
    }
  }

  const score =
    typeof movie.final_score === "number"
      ? movie.final_score.toFixed(2)
      : movie.final_score ?? 0;

  return (
    <section className="relative overflow-hidden">
      {movie.poster && (
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-cover bg-top opacity-40 blur-sm"
          style={{ backgroundImage: `url(${POSTER_HERO_URL}${movie.poster})` }}
        />
      )}
      <div className="absolute inset-0 -z-10 bg-gradient-to-b from-neutral-950/40 via-neutral-950/85 to-neutral-950" />

      <div className="mx-auto flex max-w-7xl flex-col-reverse gap-8 px-6 pb-20 pt-12 md:flex-row md:items-end">
        <div className="flex-1">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-amber-400">
            <SparkleIcon className="h-3.5 w-3.5" /> Top pick for you
          </div>

          <h2 className="mb-3 text-4xl font-black tracking-tight md:text-5xl">
            {movie.title}
          </h2>

          {(movie.genres || movie.director) && (
            <p className="mb-4 text-sm text-neutral-400">
              {movie.genres}
              {movie.genres && movie.director ? "  ·  " : ""}
              {movie.director}
            </p>
          )}

          {movie.overview && (
            <p className="mb-6 max-w-2xl text-neutral-300 line-clamp-3">
              {movie.overview}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleClick}
              className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-2.5 font-medium text-neutral-900 transition hover:bg-neutral-200"
            >
              <PlayIcon className="h-4 w-4" /> View details
            </button>

            <span className="rounded-full border border-neutral-700 bg-neutral-900/60 px-3 py-1 text-xs text-neutral-300">
              Hybrid score {score}
            </span>

            {movie.reason && (
              <span className="rounded-full border border-emerald-900/60 bg-emerald-900/20 px-3 py-1 text-xs text-emerald-300">
                {movie.reason}
              </span>
            )}
          </div>
        </div>

        {movie.poster && (
          <div className="self-center md:self-end">
            <img
              src={`${POSTER_BASE_URL}${movie.poster}`}
              alt={movie.title}
              className="h-72 w-48 rounded-2xl object-cover shadow-2xl shadow-black/60 ring-1 ring-neutral-800"
            />
          </div>
        )}
      </div>
    </section>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section>
      <header className="mb-5">
        <h2 className="text-2xl font-bold tracking-tight text-neutral-100">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-neutral-400">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-5 py-2 text-sm font-medium transition ${
        active
          ? "bg-white text-neutral-950 shadow"
          : "text-neutral-400 hover:text-neutral-100"
      }`}
    >
      {children}
    </button>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-neutral-800 bg-neutral-900/30 p-10 text-center text-sm text-neutral-500">
      {message}
    </div>
  );
}

type ChipVariant = "include" | "exclude" | "director" | "tone" | "neutral";

function Chip({
  children,
  variant,
}: {
  children: ReactNode;
  variant: ChipVariant;
}) {
  const styles: Record<ChipVariant, string> = {
    include: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
    exclude: "bg-red-500/10 text-red-300 border-red-500/30",
    director: "bg-purple-500/10 text-purple-300 border-purple-500/30",
    tone: "bg-amber-500/10 text-amber-300 border-amber-500/30",
    neutral: "bg-neutral-800 text-neutral-300 border-neutral-700",
  };
  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-medium ${styles[variant]}`}>
      {children}
    </span>
  );
}

function HistoryCard({ movie }: { movie: HistoryItem }) {
  return (
    <div className="group relative overflow-hidden rounded-xl bg-neutral-900 ring-1 ring-neutral-800 transition hover:ring-neutral-600">
      {movie.poster ? (
        <img
          src={`${POSTER_BASE_URL}${movie.poster}`}
          alt={movie.title}
          className="aspect-[2/3] w-full object-cover transition duration-500 group-hover:scale-105"
        />
      ) : (
        <div className="flex aspect-[2/3] items-center justify-center bg-neutral-800 text-xs text-neutral-500">
          No poster
        </div>
      )}

      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-neutral-950 via-neutral-950/85 to-transparent p-3">
        <h3 className="truncate text-sm font-semibold text-neutral-100">{movie.title}</h3>
        {movie.genres && (
          <p className="mt-0.5 truncate text-xs text-neutral-400">{movie.genres}</p>
        )}
      </div>
    </div>
  );
}

function StarIcon({
  filled,
  className = "",
}: {
  filled: boolean;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinejoin="round"
        d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"
      />
    </svg>
  );
}

function StarRating({ onRate }: { onRate: (rating: number) => void }) {
  const [hover, setHover] = useState(0);
  const [rated, setRated] = useState(0);

  const display = hover || rated;

  function handleClick(rating: number) {
    setRated(rating);
    onRate(rating);
  }

  return (
    <div
      className="flex items-center gap-1"
      onMouseLeave={() => setHover(0)}
    >
      {[1, 2, 3, 4, 5].map((r) => (
        <button
          key={r}
          type="button"
          onMouseEnter={() => setHover(r)}
          onClick={() => handleClick(r)}
          className={`transition ${
            r <= display ? "text-amber-400" : "text-neutral-600 hover:text-amber-400/70"
          }`}
          aria-label={`Rate ${r} star${r > 1 ? "s" : ""}`}
        >
          <StarIcon filled={r <= display} className="h-5 w-5" />
        </button>
      ))}
    </div>
  );
}

function SparkleIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 2l1.8 5.4L19 9l-5.2 1.6L12 16l-1.8-5.4L5 9l5.2-1.6z" />
    </svg>
  );
}

function PlayIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function CloseIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" />
    </svg>
  );
}

function RecommendationCard({
  movie,
  userId,
  source,
  onInteraction,
}: {
  movie: RecommendationItem;
  userId: number;
  source: string;
  onInteraction?: () => void;
}) {
  const [showDetails, setShowDetails] = useState(false);

  async function handleMovieClick() {
    try {
      await logInteractionEvent({
        user_id: userId,
        movie_id: movie.movieId,
        event_type: "movie_click",
        event_value: 1.0,
        source,
        rank: movie.rank,
        metadata: { title: movie.title, source },
      });
      onInteraction?.();
    } catch (err) {
      console.error("Failed to log movie_click:", err);
    }
  }

  async function handleRating(rating: number) {
    try {
      await logInteractionEvent({
        user_id: userId,
        movie_id: movie.movieId,
        event_type: "movie_rating",
        event_value: rating,
        source,
        rank: movie.rank,
        metadata: { title: movie.title, source, rating_ui: "star_rating" },
      });
      onInteraction?.();
    } catch (err) {
      console.error("Failed to log movie_rating:", err);
    }
  }

  async function handleDislike() {
    try {
      await logInteractionEvent({
        user_id: userId,
        movie_id: movie.movieId,
        event_type: "movie_dislike",
        event_value: 0.0,
        source,
        rank: movie.rank,
        metadata: { title: movie.title, source },
      });
      onInteraction?.();
    } catch (err) {
      console.error("Failed to log movie_dislike:", err);
    }
  }

  return (
    <article className="group relative flex flex-col overflow-hidden rounded-2xl bg-neutral-900 ring-1 ring-neutral-800 transition hover:ring-neutral-600">
      {/* Poster */}
      <div className="relative">
        <button
          type="button"
          onClick={handleMovieClick}
          className="block w-full text-left"
        >
          {movie.poster ? (
            <img
              src={`${POSTER_BASE_URL}${movie.poster}`}
              alt={movie.title}
              className="aspect-[2/3] w-full object-cover transition duration-500 group-hover:scale-105"
            />
          ) : (
            <div className="flex aspect-[2/3] items-center justify-center bg-neutral-800 text-sm text-neutral-500">
              No poster
            </div>
          )}
        </button>

        {/* Rank badge */}
        <span className="absolute left-3 top-3 rounded-full bg-neutral-950/80 px-2.5 py-1 text-xs font-bold text-amber-400 backdrop-blur">
          #{movie.rank}
        </span>

        {/* Dislike button */}
        <button
          type="button"
          onClick={handleDislike}
          aria-label="Not interested"
          title="Not interested"
          className="absolute right-3 top-3 rounded-full bg-neutral-950/80 p-1.5 text-neutral-300 backdrop-blur transition hover:bg-red-600 hover:text-white"
        >
          <CloseIcon className="h-4 w-4" />
        </button>

        {/* Hover overlay with reason */}
        {movie.reason && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 translate-y-full bg-gradient-to-t from-neutral-950 via-neutral-950/90 to-transparent p-3 text-xs text-emerald-300 transition duration-300 group-hover:translate-y-0">
            ✦ {movie.reason}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col p-4">
        <h3 className="truncate text-base font-semibold text-neutral-100">
          {movie.title}
        </h3>
        {movie.genres && (
          <p className="mt-1 truncate text-xs text-neutral-400">{movie.genres}</p>
        )}
        {movie.director && (
          <p className="mt-0.5 truncate text-xs text-neutral-500">
            Dir. {movie.director}
          </p>
        )}
        {movie.overview && (
          <p className="mt-3 line-clamp-3 text-xs leading-relaxed text-neutral-400">
            {movie.overview}
          </p>
        )}

        {/* Rating + scores toggle */}
        <div className="mt-4 flex items-center justify-between border-t border-neutral-800 pt-3">
          <StarRating onRate={handleRating} />
          <button
            type="button"
            onClick={() => setShowDetails((v) => !v)}
            className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500 transition hover:text-neutral-200"
          >
            {showDetails ? "Hide scores" : "Scores"}
          </button>
        </div>

        {/* Score breakdown */}
        {showDetails && (
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 rounded-lg bg-neutral-950/60 p-3 text-[11px] text-neutral-400">
            <ScoreRow label="Content" value={movie.content_score} />
            <ScoreRow label="CF" value={movie.cf_score} />
            <ScoreRow label="Hybrid" value={movie.final_score} />
            <ScoreRow label="Dynamic" value={movie.dynamic_score ?? movie.final_score} />
            {movie.recent_interest_score !== undefined && (
              <ScoreRow label="Recent" value={movie.recent_interest_score} />
            )}
            {movie.support_count !== undefined && (
              <ScoreRow label="Support" value={movie.support_count} />
            )}
          </dl>
        )}
      </div>
    </article>
  );
}

function ScoreRow({
  label,
  value,
}: {
  label: string;
  value: number | undefined;
}) {
  const display =
    typeof value === "number" ? Number(value.toFixed(3)) : value ?? 0;
  return (
    <div className="flex items-center justify-between">
      <dt className="text-neutral-500">{label}</dt>
      <dd className="font-mono text-neutral-200">{display}</dd>
    </div>
  );
}
