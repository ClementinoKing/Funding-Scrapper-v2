import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function HomePage() {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col justify-center px-4 py-16">
      <p className="mb-4 inline-flex w-fit rounded-full border bg-white/70 px-3 py-1 text-xs font-semibold">
        Funding Program Discovery and Matching Platform
      </p>
      <h1 className="max-w-3xl text-4xl font-extrabold tracking-tight md:text-5xl">
        Discover funding opportunities you actually qualify for.
      </h1>
      <p className="mt-5 max-w-2xl text-base text-muted-foreground md:text-lg">
        Automated daily scraping, structured data normalization, rule-based matching, and admin oversight in one extensible system.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Button asChild size="lg">
          <Link to="/auth/login">
            Sign in to platform
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link to="/auth/register">Create account</Link>
        </Button>
      </div>

      <div className="mt-10 grid gap-4 md:grid-cols-3">
        {[
          "Applicant dashboard with profile and instant matches",
          "Scraper ingestion monitoring and confidence triage",
          "Admin review queue with intervention workflows"
        ].map((text) => (
          <Card key={text}>
            <CardContent className="p-5 text-sm text-muted-foreground">{text}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
