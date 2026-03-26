import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const queue = [
  {
    id: "case_001",
    user: "User #001",
    reason: "High profile completeness but no high-fit matches",
    status: "open"
  },
  {
    id: "case_002",
    user: "User #143",
    reason: "Low confidence on deadline extraction",
    status: "in_progress"
  }
];

export function InterventionsPage() {
  return (
    <div>
      <SectionHeader
        title="Manual Intervention Queue"
        description="Resolve exceptions, manually link opportunities, and trigger notification workflows."
      />
      <div className="space-y-4">
        {queue.map((item) => (
          <Card key={item.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{item.id}</CardTitle>
                <Badge variant={item.status === "open" ? "warning" : "secondary"}>{item.status}</Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm md:flex-row md:items-center md:justify-between">
              <div>
                <p className="font-semibold">{item.user}</p>
                <p className="text-muted-foreground">{item.reason}</p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">Open case</Button>
                <Button size="sm">Assign program</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
