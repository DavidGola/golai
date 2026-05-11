import { z } from 'zod'

export const ProposalActionTypeSchema = z.enum([
  'add_to_library',
  'change_status',
  'set_rating',
  'remove_from_library',
])

export const ProposalStateSchema = z.enum(['pending', 'confirmed', 'cancelled'])

export const ProposalReadSchema = z.object({
  id: z.string(),
  message_id: z.string(),
  action_type: ProposalActionTypeSchema,
  payload: z.record(z.string(), z.unknown()),
  state: ProposalStateSchema,
  state_changed_at: z.string().nullable(),
  created_at: z.string(),
})

export type ProposalActionType = z.infer<typeof ProposalActionTypeSchema>
export type ProposalState = z.infer<typeof ProposalStateSchema>
export type ProposalRead = z.infer<typeof ProposalReadSchema>
