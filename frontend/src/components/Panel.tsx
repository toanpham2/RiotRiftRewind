import React from "react";

type Props = React.HTMLAttributes<HTMLDivElement> & { title?: string };
export default function Panel({ title, className="", children, ...rest }: Props) {
  return (
      <section
          {...rest}
          className={[
            "relative rounded-[18px] border-2 border-lolGold/80",
            "bg-lolCard/80 backdrop-blur",
            "shadow-lolOuter",
            className,
          ].join(" ")}
      >
        {/* top gold hairline */}
        <div className="absolute inset-x-0 top-0 h-[3px] rounded-t-[18px] bg-gradient-to-r from-lolGold/35 via-lolGold to-lolGold/35" />
        {title && (
            <header className="border-b border-white/10 px-6 py-3">
              <h2 className="font-display tracking-wider text-xl text-lolGold">{title}</h2>
            </header>
        )}
        <div className="p-6">{children}</div>
      </section>
  );
}
