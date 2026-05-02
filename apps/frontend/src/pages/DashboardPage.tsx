import { useEffect, useState } from "react";
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

const POSTER_BASE_URL = "https://image.tmdb.org/t/p/w300";

type TabKey = "history" | "hybrid" | "preferences";

export default function DashboardPage() {
  const navigate = useNavigate();

  const [userId, setUserId] = useState<number | null>(null);

  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [hybridRecommendations, setHybridRecommendations] = useState<RecommendationItem[]>([]);
  const [preferenceRecommendations, setPreferenceRecommendations] = useState<RecommendationItem[]>([]);

  const [activeTab, setActiveTab] = useState<TabKey>("history");

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

  if (loading) {
    return <div className="p-6 text-slate-700">Loading dashboard...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-slate-900">
              MovieReco Dashboard
            </h1>
            <p className="mt-1 text-sm text-slate-600">User ID: {userId}</p>
          </div>

          <button
            onClick={handleLogout}
            className="rounded-xl bg-slate-900 px-4 py-2 text-white hover:bg-slate-800"
          >
            Logout
          </button>
        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">
            {error}
          </div>
        )}

        <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-3 md:flex-row">
            <input
              value={preferenceText}
              onChange={(e) => setPreferenceText(e.target.value)}
              placeholder='Describe what you want (e.g. "dark thriller, no sci-fi")'
              className="flex-1 rounded-xl border border-slate-300 px-3 py-2"
            />

            <button
              onClick={handlePreferenceSearch}
              disabled={isRefining}
              className="rounded-xl bg-slate-900 px-4 py-2 text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isRefining ? "Refining..." : "Refine"}
            </button>

            <button
              onClick={handleResetHybrid}
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Reset to Hybrid
            </button>
          </div>

          {refineError && (
            <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {refineError}
            </div>
          )}

          {parsedPrefs && (
            <div className="mt-4">
              <p className="mb-2 text-sm text-slate-600">Detected preferences:</p>

              <div className="flex flex-wrap gap-2">
                {parsedPrefs.include_genres?.map((g) => (
                  <span
                    key={`include-${g}`}
                    className="rounded bg-blue-100 px-2 py-1 text-sm text-blue-700"
                  >
                    {g}
                  </span>
                ))}

                {parsedPrefs.exclude_genres?.map((g) => (
                  <span
                    key={`exclude-${g}`}
                    className="rounded bg-red-100 px-2 py-1 text-sm text-red-700"
                  >
                    No {g}
                  </span>
                ))}

                {parsedPrefs.preferred_directors?.map((d) => (
                  <span
                    key={`director-${d}`}
                    className="rounded bg-purple-100 px-2 py-1 text-sm text-purple-700"
                  >
                    {d}
                  </span>
                ))}

                {parsedPrefs.tone?.map((t) => (
                  <span
                    key={`tone-${t}`}
                    className="rounded bg-green-100 px-2 py-1 text-sm text-green-700"
                  >
                    {t}
                  </span>
                ))}

                {parsedPrefs.keywords?.map((k) => (
                  <span
                    key={`keyword-${k}`}
                    className="rounded bg-slate-100 px-2 py-1 text-sm text-slate-700"
                  >
                    {k}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>

        <div className="mb-6 flex gap-3 border-b border-slate-200">
          <button
            onClick={() => setActiveTab("history")}
            className={`rounded-t-xl px-4 py-2 text-sm font-medium ${
              activeTab === "history"
                ? "border border-b-0 border-slate-200 bg-white text-slate-900"
                : "text-slate-500 hover:text-slate-900"
            }`}
          >
            Watch History
          </button>

          <button
            onClick={() => setActiveTab("hybrid")}
            className={`rounded-t-xl px-4 py-2 text-sm font-medium ${
              activeTab === "hybrid"
                ? "border border-b-0 border-slate-200 bg-white text-slate-900"
                : "text-slate-500 hover:text-slate-900"
            }`}
          >
            Hybrid Recommendations
          </button>

          <button
            onClick={() => setActiveTab("preferences")}
            className={`rounded-t-xl px-4 py-2 text-sm font-medium ${
              activeTab === "preferences"
                ? "border border-b-0 border-slate-200 bg-white text-slate-900"
                : "text-slate-500 hover:text-slate-900"
            }`}
          >
            Preference Recommendations
          </button>
        </div>

        {activeTab === "history" && (
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-xl font-semibold text-slate-900">Watch History</h2>
            <p className="mt-1 text-sm text-slate-500">Movies you have liked.</p>

            <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {history.length === 0 ? (
                <p className="text-sm text-slate-500">No history found.</p>
              ) : (
                history.map((movie) => (
                  <div
                    key={`${movie.movieId}-${movie.timestamp ?? "na"}`}
                    className="overflow-hidden rounded-2xl border border-slate-200 bg-white"
                  >
                    {movie.poster ? (
                      <img
                        src={`${POSTER_BASE_URL}${movie.poster}`}
                        alt={movie.title}
                        className="h-72 w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-72 items-center justify-center bg-slate-100 text-sm text-slate-400">
                        No poster available
                      </div>
                    )}

                    <div className="p-4">
                      <h3 className="text-lg font-semibold text-slate-900">
                        {movie.title}
                      </h3>

                      {movie.genres && (
                        <p className="mt-2 text-sm text-slate-600">{movie.genres}</p>
                      )}

                      {movie.director && (
                        <p className="mt-2 text-sm text-slate-500">
                          Director: {movie.director}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        )}

        {activeTab === "hybrid" && (
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-xl font-semibold text-slate-900">
              Hybrid Recommendations
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Recommendations from the hybrid collaborative + content model.
            </p>

            <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {hybridRecommendations.length === 0 ? (
                <p className="text-sm text-slate-500">No recommendations found.</p>
              ) : (
                hybridRecommendations.map((movie) => (
                    <RecommendationCard
                      key={`hybrid-${movie.movieId}`}
                      movie={movie}
                      userId={userId!}
                      source="hybrid_recommendations"
                      onInteraction={refreshHybridRecommendations}
                    />
                  ))
              )}
            </div>
          </section>
        )}

        {activeTab === "preferences" && (
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-xl font-semibold text-slate-900">
              Preference Recommendations
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Recommendations refined using your current free-text preference.
            </p>

            <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {preferenceRecommendations.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No refined recommendations yet. Enter a preference above and click Refine.
                </p>
              ) : (
                preferenceRecommendations.map((movie) => (
                    <RecommendationCard
                      key={`pref-${movie.movieId}`}
                      movie={movie}
                      userId={userId!}
                      source="preference_recommendations"
                      onInteraction={refreshHybridRecommendations}
                    />
                  ))
              )}
            </div>
          </section>
        )}
      </div>
    </div>
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
    async function handleMovieClick() {
      try {
        await logInteractionEvent({
          user_id: userId,
          movie_id: movie.movieId,
          event_type: "movie_click",
          event_value: 1.0,
          source,
          rank: movie.rank,
          metadata: {
            title: movie.title,
            source,
          },
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
          metadata: {
            title: movie.title,
            source,
            rating_ui: "button_rating",
          },
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
          metadata: {
            title: movie.title,
            source,
          },
        });
  
        onInteraction?.();
      } catch (err) {
        console.error("Failed to log movie_dislike:", err);
      }
    }
  
    return (
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <button
          type="button"
          onClick={handleMovieClick}
          className="block w-full text-left"
        >
          {movie.poster ? (
            <img
              src={`${POSTER_BASE_URL}${movie.poster}`}
              alt={movie.title}
              className="h-72 w-full object-cover"
            />
          ) : (
            <div className="flex h-72 items-center justify-center bg-slate-100 text-sm text-slate-400">
              No poster available
            </div>
          )}
        </button>
  
        <div className="p-4">
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-lg font-semibold text-slate-900">
              {movie.title}
            </h3>
  
            <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
              #{movie.rank}
            </span>
          </div>
  
          {movie.genres && (
            <p className="mt-2 text-sm text-slate-600">{movie.genres}</p>
          )}
  
          {movie.director && (
            <p className="mt-2 text-sm text-slate-500">
              Director: {movie.director}
            </p>
          )}
  
          {movie.overview && (
            <p className="mt-3 line-clamp-4 text-sm text-slate-700">
              {movie.overview}
            </p>
          )}
  
          <div className="mt-4 space-y-1 text-xs text-slate-500">
            <div className="flex items-center justify-between">
              <span>Content: {movie.content_score ?? 0}</span>
              <span>CF: {movie.cf_score ?? 0}</span>
            </div>
  
            <div className="flex items-center justify-between">
              <span>Hybrid: {movie.final_score ?? 0}</span>
              <span>Dynamic: {movie.dynamic_score ?? movie.final_score ?? 0}</span>
            </div>
  
            {movie.recent_interest_score !== undefined && (
              <div className="flex items-center justify-between">
                <span>Recent interest:</span>
                <span>{movie.recent_interest_score}</span>
              </div>
            )}
  
            {movie.support_count !== undefined && (
              <div className="flex items-center justify-between">
                <span>Support:</span>
                <span>{movie.support_count}</span>
              </div>
            )}
          </div>
  
          {movie.reason && (
            <p className="mt-3 text-xs text-green-700">{movie.reason}</p>
          )}
  
          <div className="mt-4 border-t border-slate-100 pt-3">
            <p className="mb-2 text-xs font-medium text-slate-500">
              Rate this movie
            </p>
  
            <div className="flex flex-wrap gap-2">
              {[1, 2, 3, 4, 5].map((rating) => (
                <button
                  key={rating}
                  type="button"
                  onClick={() => handleRating(rating)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
                >
                  {rating}★
                </button>
              ))}
  
              <button
                type="button"
                onClick={handleDislike}
                className="rounded-lg border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
              >
                Dislike
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }