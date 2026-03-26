import { SectionHeader } from "@/components/shared/section-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export function MatchingRulesPage() {
  return (
    <div>
      <SectionHeader
        title="Matching Engine Controls"
        description="Adjust rule weights, trigger recalculations, and monitor confidence thresholds."
      />
      <Card>
        <CardHeader>
          <CardTitle>Rule Weight Configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Sector overlap weight</Label>
            <Input defaultValue="35" />
          </div>
          <div className="space-y-2">
            <Label>Geography weight</Label>
            <Input defaultValue="30" />
          </div>
          <div className="space-y-2">
            <Label>Funding type weight</Label>
            <Input defaultValue="20" />
          </div>
          <div className="space-y-2">
            <Label>Amount range weight</Label>
            <Input defaultValue="15" />
          </div>
          <div className="md:col-span-2 flex gap-3">
            <Button>Save weights</Button>
            <Button variant="outline">Re-run matching job</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
