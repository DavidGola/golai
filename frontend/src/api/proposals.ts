import { apiClient } from '@/lib/apiClient'
import { ProposalReadSchema, type ProposalRead } from '@/types/proposal'

export async function confirmProposal(id: string): Promise<ProposalRead> {
  const res = await apiClient.post<unknown>(`/proposals/${id}/confirm`)
  return ProposalReadSchema.parse(res.data)
}

export async function cancelProposal(id: string): Promise<ProposalRead> {
  const res = await apiClient.post<unknown>(`/proposals/${id}/cancel`)
  return ProposalReadSchema.parse(res.data)
}
