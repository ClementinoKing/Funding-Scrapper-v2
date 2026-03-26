import { useQuery } from "@tanstack/react-query";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/services/api/client";

export function NotificationsPage() {
  const { data: preferences } = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => apiClient.getNotificationPreferences("user_001")
  });

  const { data: events = [] } = useQuery({
    queryKey: ["notification-events"],
    queryFn: () => apiClient.getNotificationEvents("user_001")
  });

  return (
    <div>
      <SectionHeader
        title="Notifications"
        description="Email-first alerts for qualified opportunities, deadline reminders, and admin updates."
      />
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Channel Preferences</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm md:grid-cols-4">
          <p>Email: <strong>{preferences?.emailEnabled ? "On" : "Off"}</strong></p>
          <p>WhatsApp: <strong>{preferences?.whatsappEnabled ? "On" : "Off"}</strong></p>
          <p>SMS: <strong>{preferences?.smsEnabled ? "On" : "Off"}</strong></p>
          <p>Frequency: <strong>{preferences?.digestFrequency}</strong></p>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {events.map((event) => (
          <Card key={event.id}>
            <CardContent className="flex items-center justify-between p-4 text-sm">
              <p>{event.type.replace("_", " ")} via {event.channel}</p>
              <Badge variant={event.status === "sent" ? "success" : "secondary"}>{event.status}</Badge>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
