import { Fraunces, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

// Display face — Fraunces. Used ONLY at H1/H2 moments (agent name, section
// titles, empty-state headlines, login headline). Never in body/UI text.
export const fraunces = Fraunces({
  subsets: ["latin"],
  axes: ["opsz", "SOFT"],
  style: ["normal", "italic"],
  variable: "--font-fraunces",
  display: "swap",
});

// Body/UI face — every control, sentence, nav item, button.
export const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
  display: "swap",
});

// Data face — anywhere digits need to line up: tokens, costs, timestamps,
// ids, audit rows. Paired with font-variant-numeric: tabular-nums.
export const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});
