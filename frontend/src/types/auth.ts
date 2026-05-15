import { z } from 'zod'
import { STORE_PLATFORMS } from '@/types/store'

export const GenreReadSchema = z.object({
  id: z.number(),
  slug: z.string(),
  name: z.string(),
  description: z.string().nullish(),
})

export const CriterionReadSchema = z.object({
  id: z.number(),
  slug: z.string(),
  name: z.string(),
  description: z.string().nullish(),
})

export const UserReadSchema = z.object({
  id: z.string(),
  email: z.string(),
  username: z.string(),
  is_active: z.boolean(),
  is_superuser: z.boolean(),
  is_verified: z.boolean(),
  preferred_playtime: z.enum(['short', 'medium', 'long']).nullable(),
  preferred_platform: z.enum(STORE_PLATFORMS).nullable().optional(),
  created_at: z.string(),
})

export const UserProfileSchema = UserReadSchema.extend({
  favorite_genres: z.array(GenreReadSchema),
  important_criteria: z.array(CriterionReadSchema),
  psn_online_id: z.string().nullable().optional(),
  last_psn_sync_at: z.string().nullable().optional(),
})

export const LoginResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
})

export type UserRead = z.infer<typeof UserReadSchema>
export type UserProfile = z.infer<typeof UserProfileSchema>
export type LoginResponse = z.infer<typeof LoginResponseSchema>
