type Star = {
  delay: number
  duration: number
  left: number
  opacity: number
  size: number
  top: number
}

type ShootingStar = {
  delay: number
  duration: number
  left: number
  top: number
}

const STARS: Star[] = Array.from({ length: 92 }, (_, index) => ({
  left: (index * 47 + (index % 7) * 13) % 100,
  top: (index * 29 + (index % 11) * 7) % 100,
  size: index % 19 === 0 ? 2 : index % 5 === 0 ? 1.5 : 1,
  opacity: 0.32 + ((index * 17) % 55) / 100,
  duration: 2.8 + (index % 6) * 0.8,
  delay: -((index * 0.73) % 7),
}))

const SHOOTING_STARS: ShootingStar[] = [
  { left: 13, top: 15, duration: 8.4, delay: -1.5 },
  { left: 57, top: 7, duration: 10.2, delay: -5.7 },
  { left: 78, top: 37, duration: 9.1, delay: -3.2 },
  { left: 37, top: 62, duration: 11.6, delay: -7.8 },
]

export function StarfieldBackground() {
  return (
    <div aria-hidden="true" className="starfield">
      <div className="starfield__glow" />
      <div className="starfield__stars">
        {STARS.map((star, index) => (
          <span
            key={index}
            className="starfield__star"
            style={{
              animationDelay: `${star.delay}s`,
              animationDuration: `${star.duration}s`,
              height: `${star.size}px`,
              left: `${star.left}%`,
              opacity: star.opacity,
              top: `${star.top}%`,
              width: `${star.size}px`,
            }}
          />
        ))}
      </div>
      {SHOOTING_STARS.map((star, index) => (
        <span
          key={index}
          className="starfield__shooting-star"
          style={{
            animationDelay: `${star.delay}s`,
            animationDuration: `${star.duration}s`,
            left: `${star.left}%`,
            top: `${star.top}%`,
          }}
        />
      ))}
    </div>
  )
}
