import React from "react";
import html2canvas from "html2canvas";

type ExportPngButtonProps = {
  /** Accept any Element to avoid RefObject invariance issues */
  target: React.RefObject<Element | null>;
  filename?: string;
  className?: string;
};

export default function ExportPngButton({
                                          target,
                                          filename = "RiftRewind.png",
                                          className = "",
                                        }: ExportPngButtonProps) {
  async function handleClick() {
    const node = target.current as HTMLElement | null;
    if (!node) return;

    const ignored = Array.from(
        document.querySelectorAll<HTMLElement>("[data-export-ignore='true']")
    );
    const prev = ignored.map((el) => el.style.display);
    ignored.forEach((el) => (el.style.display = "none"));

    try {
      const canvas = await html2canvas(node, {
        backgroundColor: "#0b0f13",
        useCORS: true,
        allowTaint: true,
        scale: window.devicePixelRatio || 2,
      });
      const url = canvas.toDataURL("image/png");
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
    } finally {
      // restore
      ignored.forEach((el, i) => (el.style.display = prev[i]));
    }
  }

  return (
      <button
          onClick={handleClick}
          className={[
            "px-3 py-1 rounded-md border-2 border-lolGold bg-[#2237a7] text-gray-100",
            "shadow-[0_0_12px_rgba(201,168,106,0.35)] hover:bg-[#1b2e92] active:bg-[#152673]",
            "transition-colors",
            className,
          ].join(" ")}
      >
        Export PNG
      </button>
  );
}
