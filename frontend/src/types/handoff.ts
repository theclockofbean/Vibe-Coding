export type HandoffStatus = "open" | "resolved" | "ignored";

export type HandoffTicket = {
  id: string;
  created_at: string;
  user_message: string;
  final_response: string;
  module?: string;
  reason?: string;
  risk_flags?: string[];
  status: HandoffStatus;
};

export type HandoffTicketListResponse = {
  items: HandoffTicket[];
  total: number;
};
