# Notification Flow

## Initial Channel
- Email only in phase 1.

## Event Sources
- New high-fit match found.
- Deadline approaching for previously matched opportunity.
- Admin-curated recommendation.

## Delivery Steps
1. Matching engine emits notification event.
2. Preferences service validates channel and digest timing.
3. Notification worker queues and sends message.
4. Delivery status updates stored in `notifications`.

## Future Channels
- Add WhatsApp and SMS providers via channel adapters while keeping event model unchanged.
