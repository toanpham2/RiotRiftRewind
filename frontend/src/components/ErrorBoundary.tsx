import React from "react";

type State = { hasError: boolean; error?: Error };

export default class ErrorBoundary extends React.Component<
    { children: React.ReactNode },
    State
> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Render error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
          <div className="fixed inset-0 z-[9999] p-4">
            <div className="max-w-2xl mx-auto rounded-lg bg-red-900/70 border border-red-400/60 p-4">
              <div className="font-semibold text-red-200 mb-2">A component crashed while rendering</div>
              <pre className="text-red-100 whitespace-pre-wrap text-sm">
              {String(this.state.error)}
            </pre>
              <div className="text-red-300 text-xs mt-2">
                Check your browser console for the stack trace.
              </div>
            </div>
          </div>
      );
    }
    return this.props.children;
  }
}
