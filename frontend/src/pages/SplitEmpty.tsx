import SplitHeader from "../components/SplitHeader";

export default function SplitEmpty() {
  return (
      <div className="min-h-screen relative overflow-hidden bg-lolBg">
        {/* Background layers */}
        <div
            className="absolute inset-0 bg-center bg-cover opacity-20"
            style={{ backgroundImage: `url('/lol-bg.jpg')` }}
            aria-hidden
        />
        <div
            className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/30 to-black/70"
            aria-hidden
        />
        <div className="absolute inset-0 lol-vignette" aria-hidden />

        <main className="relative z-10">
          <div className="max-w-5xl mx-auto p-6 space-y-6">
            <SplitHeader title="Split 1" />

            <section
                className="
              rounded-[18px]
              border-2 border-lolGold
              bg-[#0b0f13]/70 backdrop-blur
              shadow-[0_0_24px_rgba(201,168,106,0.35)]
              p-10 text-center
            "
            >
              {/* top accent bar */}
              <div className="h-[3px] w-full rounded-t-[18px] bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40 mb-6" />

              {/* Placeholder Zilean art box */}
              <div className="mx-auto mb-6 h-40 w-40 rounded-xl bg-white/5 border border-white/15" />

              <h2 className="text-xl font-extrabold text-lolGold mb-2">
                Even Zilean can’t rewind this far…
              </h2>
              <p className="text-gray-300">
                We couldn’t retrieve valid games for Split&nbsp;1. Check your Riot ID or jump to the next
                splits below.
              </p>
            </section>
          </div>
        </main>
      </div>
  );
}
