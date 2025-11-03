export default function GoldCard({
                                   children, className = "", header,
                                 }: { children: React.ReactNode; className?: string; header?: React.ReactNode }) {
  return (
      <section
          className={[
            "rounded-xl border-2 border-lolGold bg-[#0b0f13]/70",
            "shadow-[0_0_24px_rgba(201,168,106,0.35),0_20px_60px_rgba(0,0,0,0.45)]",
            className,
          ].join(" ")}
      >
        {header && (
            <div className="h-[3px] w-full rounded-t-xl bg-gradient-to-r from-lolGold/40 via-lolGold to-lolGold/40" />
        )}
        <div className="p-5">{children}</div>
      </section>
  );
}
