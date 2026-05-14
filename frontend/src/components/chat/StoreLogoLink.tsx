import { useState } from 'react'
import { STORE_LABEL } from '@/lib/storeLinks'
import type { StorePlatform } from '@/types/store'

import steamSvg from '@/assets/stores/steam.svg'
import epicSvg from '@/assets/stores/epic.svg'
import gogSvg from '@/assets/stores/gog.svg'
import xboxSvg from '@/assets/stores/xbox.svg'
import playstationSvg from '@/assets/stores/playstation.svg'
import nintendoSvg from '@/assets/stores/nintendo.svg'

const STORE_ICON: Record<StorePlatform, string> = {
  steam: steamSvg,
  epic: epicSvg,
  gog: gogSvg,
  xbox: xboxSvg,
  playstation: playstationSvg,
  nintendo: nintendoSvg,
}

interface Props {
  platform: StorePlatform
  url: string
}

export default function StoreLogoLink({ platform, url }: Props) {
  const [hovered, setHovered] = useState(false)

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={STORE_LABEL[platform]}
      title={STORE_LABEL[platform]}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 22,
        height: 22,
        flexShrink: 0,
        opacity: hovered ? 1 : 0.55,
        transition: 'opacity 0.15s',
      }}
    >
      <img
        src={STORE_ICON[platform]}
        alt=""
        aria-hidden="true"
        style={{
          width: 16,
          height: 16,
          objectFit: 'contain',
          filter: hovered ? 'brightness(0) invert(1) sepia(1) saturate(4) hue-rotate(200deg)' : 'brightness(0) invert(0.6)',
        }}
      />
    </a>
  )
}
