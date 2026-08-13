import type { Metadata } from "next";
import "./globals.css";
import ShellLayout from "./ShellLayout";

export const metadata: Metadata = {
  title: "E-Rakshak | Investigation Command Center",
  description: "Financial Cybercrime Investigation Command Center",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased font-sans">
        <ShellLayout>{children}</ShellLayout>
      </body>
    </html>
  );
}
