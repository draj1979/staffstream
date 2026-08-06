"use client";

import { Component, type ReactNode } from "react";
import { Button } from "./Button";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // eslint-disable-next-line no-console
    console.error("StaffStream screen crashed:", error);
  }

  handleReset = () => {
    this.setState({ hasError: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[240px] flex-col items-center justify-center gap-3 rounded-md border border-crimson/30 bg-crimson/5 p-8 text-center">
          <h2 className="font-display text-xl">{this.props.fallbackTitle ?? "This screen hit a snag"}</h2>
          <p className="max-w-sm text-sm text-text-muted">
            Something broke while rendering this page. Your data is safe — try again, or come back to
            this screen in a moment.
          </p>
          <Button variant="secondary" size="sm" onClick={this.handleReset}>
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
