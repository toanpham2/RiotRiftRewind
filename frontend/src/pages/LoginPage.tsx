import { useState } from "react";
import type { YearSummary } from "../types/year";
import { fetchYearSummaryByRiotId } from "../api/client";
import { Skeleton } from "../components/Skeleton";

type Props = {
  onSuccess: (data: YearSummary) => void;
};

export default function LoginPage({ onSuccess }: Props) {
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);


  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // Ensure exactly one leading '#'
      const cleanedTag = `#${tag.replace(/^#*/, "")}`;

      const data = (await fetchYearSummaryByRiotId(
          name.trim(),
          cleanedTag
      )) as YearSummary;

      onSuccess(data);
    } catch (err: any) {
      setError(err?.message ?? "Failed to fetch summary");
    } finally {
      setLoading(false);
    }
  }

  return (
      <div className="min-h-screen relative overflow-hidden bg-lolBg">
        {/* Background image + gradients */}
        <div
            className="absolute inset-0 bg-center bg-cover opacity-35"
            style={{ backgroundImage: `url('/lol-bg.jpg')` }}
            aria-hidden
        />
        <div
            className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/40 to-black/80"
            aria-hidden
        />
        <div className="absolute inset-0 lol-vignette" aria-hidden />

        {/* Centered panel */}
        <main className="relative z-10 min-h-screen flex items-center justify-center p-6">
          <section
              className="
            w-full max-w-2xl
            rounded-[18px]
            border-2 border-lolGold
            bg-[#0b0f13]/70 backdrop-blur
            shadow-[0_0_24px_rgba(201,168,106,0.45),0_20px_60px_rgba(0,0,0,0.55)]
          "
          >
            {/* top accent bar */}
            <div className="h-[3px] w-full rounded-t-[18px] bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40" />

            {/* Title */}
            <header className="px-8 pt-8 pb-4 text-center">
              <h1 className="text-3xl font-extrabold tracking-wide text-lolGold drop-shadow">
                Rift Rewind
              </h1>
              <p className="mt-2 text-gray-300">
                Enter your Riot <span className="text-gray-100 font-medium">name</span> and{" "}
                <span className="text-gray-100 font-medium">tag</span>, then hit <em>Rewind</em>.
              </p>
            </header>

            {/* Form */}
            <form onSubmit={onSubmit} className="px-8 pb-8 pt-2 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <LabeledInput
                    label="Name"
                    placeholder="MK1Paris"
                    value={name}
                    onChange={setName}
                    disabled={loading}
                />
                <LabeledInput
                    label="Tag"
                    placeholder="#NA1"
                    value={tag}
                    onChange={setTag}
                    disabled={loading}
                />
              </div>

              {error && (
                  <div
                      role="alert"
                      className="rounded-md border border-red-500/50 bg-red-500/10 text-red-200 px-3 py-2"
                  >
                    {error}
                  </div>
              )}

              <div className="flex items-center gap-4">
                <GlowButton type="submit" disabled={loading || !name || !tag}>
                  {loading ? "Rewinding…" : "Rewind!"}
                </GlowButton>
                <span className="text-sm text-gray-400">
                Example: <span className="text-gray-200">MK1Paris</span> /{" "}
                  <span className="text-gray-200">#NA1</span>
              </span>
              </div>

              {/* Skeletons while we wait (LoL client vibe) */}
              {loading && (
                  <div className="mt-2 space-y-3">
                    <Skeleton className="h-6 w-3/4" />
                    <Skeleton className="h-6 w-2/3" />
                    <Skeleton className="h-6 w-5/6" />
                  </div>
              )}

            </form>
          </section>
        </main>
      </div>
  );
}

/* ---------- UI subcomponents ---------- */

function LabeledInput(props: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const { label, placeholder, value, onChange, disabled } = props;
  return (
      <label className="block">
        <span className="text-sm text-gray-300">{label}</span>
        <div
            className="
          mt-1 rounded-xl
          border-2 border-lolGold
          bg-[#0f1419]
          shadow-[inset_0_0_10px_rgba(201,168,106,0.15)]
          focus-within:ring-2 focus-within:ring-lolBlue focus-within:border-lolBlue
        "
        >
          <input
              disabled={disabled}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={placeholder}
              className="w-full px-3 py-2 rounded-xl bg-transparent text-gray-100 placeholder:text-gray-500 outline-none border-0"
              autoComplete="off"
          />
        </div>
      </label>
  );
}

function GlowButton(
    props: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: React.ReactNode }
) {
  const { children, className = "", ...rest } = props;
  return (
      <button
          {...rest}
          className={[
            "relative inline-flex items-center justify-center",
            "px-5 py-2 rounded-xl select-none",
            "bg-[#2237a7] hover:bg-[#1b2e92] active:bg-[#152673]",
            "border-2 border-lolGold",
            "shadow-[0_0_18px_rgba(201,168,106,0.35)]",
            "transition-all duration-200",
            "disabled:opacity-60 disabled:cursor-not-allowed",
            "overflow-hidden group",
            className,
          ].join(" ")}
      >
        {/* sheen */}
        <span className="pointer-events-none absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <span className="absolute -inset-x-10 -top-1 h-1/2 bg-gradient-to-r from-transparent via-white/25 to-transparent blur-md" />
      </span>
        <span className="text-sm font-semibold text-gray-100 tracking-wide">{children}</span>
      </button>
  );
}
