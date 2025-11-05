import type { YearSummary } from "../types/year";
import SplitEmpty from "./SplitEmpty";
import SplitPage from "./SplitPage";
import YearRecap from "./YearRecap";



export default function SplitsRouter({ data }: { data: YearSummary }) {
  const { s1, s2, s3 } = data.splits;
  const { year } = data;

  return (
      <div className="space-y-16">
        {/* Split 1: show Zilean apology if no data */}
        {!s1.overall && <SplitEmpty />}

        {/* Split 2 and 3 */}
        <SplitPage split={s2} />
        <SplitPage split={s3} />

        {/* Year-end recap */}
        {year && <YearRecap data={data} />}
        {/* pass the full YearSummary so Recap can use both year and splits */}
      </div>
  );
}
