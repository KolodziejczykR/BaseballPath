import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PublicCardClient } from "@/components/player-card/public-card-client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Props = { params: Promise<{ slug: string }> };

type PublicCardData = {
  display_name: string;
  primary_position?: string;
  prediction_level?: string;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const response = await fetch(`${API_BASE_URL}/p/${slug}/data`, { cache: "no-store" });
  if (!response.ok) {
    return { title: "BaseballPath" };
  }

  const card = (await response.json()) as PublicCardData;
  const title = `${card.display_name} - ${card.primary_position || "Player"} | BaseballPath`;
  const description = `${card.prediction_level || "Prospect"} profile. View stats and profile.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      images: [`${API_BASE_URL}/p/${slug}/og-image`],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [`${API_BASE_URL}/p/${slug}/og-image`],
    },
  };
}

export default async function PublicCardPage({ params }: Props) {
  const { slug } = await params;
  const response = await fetch(`${API_BASE_URL}/p/${slug}/data`, { cache: "no-store" });

  if (!response.ok) {
    notFound();
  }

  const card = (await response.json()) as PublicCardData;

  return (
    <main className="min-h-screen px-6 py-12">
      <div className="mx-auto max-w-5xl">
        <p className="text-center text-xs uppercase tracking-[0.3em] text-[var(--muted)]">Public Player Card</p>
        <h1 className="display-font mt-3 text-center text-4xl md:text-5xl">{card.display_name}</h1>
        <p className="mt-2 text-center text-[var(--muted)]">
          {card.primary_position || "Position unavailable"} · {card.prediction_level || "Prospect"}
        </p>

        <PublicCardClient card={card} />
      </div>
    </main>
  );
}
