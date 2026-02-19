import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** If true, renders a compact inline fallback instead of full-page */
  inline?: boolean;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary] Caught error:", error);
    console.error("[ErrorBoundary] Component stack:", info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    // Compact inline variant — for sidebar sections so they don't crash the recording
    if (this.props.inline) {
      return (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-center">
          <p className="text-sm font-medium text-amber-800">
            This section encountered an issue
          </p>
          <p className="mt-1 text-xs text-amber-600">
            The rest of the application is unaffected.
          </p>
          <button
            onClick={this.handleReset}
            className="mt-3 rounded-md bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800 transition-colors hover:bg-amber-200"
          >
            Try Again
          </button>
        </div>
      );
    }

    // Full-page fallback
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="w-full max-w-md text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-amber-100">
            <svg
              className="h-7 w-7 text-amber-600"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
              />
            </svg>
          </div>

          <h2 className="mb-2 text-lg font-semibold text-slate-900">
            Something went wrong
          </h2>
          <p className="mb-1 text-sm text-slate-500">
            An unexpected error occurred. Your session data has not been lost.
          </p>
          <p className="mb-6 text-xs font-mono text-slate-400">
            {this.state.error?.message ?? "Unknown error"}
          </p>

          <div className="flex items-center justify-center gap-3">
            <button
              onClick={this.handleReset}
              className="rounded-lg bg-clinical-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-clinical-700"
            >
              Try Again
            </button>
            <a
              href="/"
              className="rounded-lg border border-slate-200 bg-white px-5 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
            >
              Return Home
            </a>
          </div>
        </div>
      </div>
    );
  }
}
