import { useState } from "react";
import LoginPage from "./pages/LoginPage";
import SplitsRouter from "./pages/SplitsRouter";
import type { YearSummary } from "./types/year";
import AppShell from "./components/AppShell";

export default function App() {
  const [data, setData] = useState<YearSummary | null>(null);

  return (
      <div className="bg-lolBg min-h-screen">
        <div className="fixed bottom-4 right-4 bg-emerald-500 text-black px-3 py-1 rounded">
          TW OK
        </div>
        <AppShell>
          {!data ? <LoginPage onSuccess={setData}/> : <SplitsRouter data={data}/>}
        </AppShell>
      </div>


  );
}
