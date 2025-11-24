import { useCallback } from "react";
import Particles from "react-tsparticles";
import { loadSlim } from "tsparticles-slim";

const StarBackground = () => {
  const particlesInit = useCallback(async (engine) => {
    await loadSlim(engine);
  }, []);

  return (
    <Particles
      id="tsparticles"
      init={particlesInit}
      options={{
        fullScreen: {
          enable: true,
          zIndex: 0
        },
        background: {
          color: {
            value: "#020617", // 深空蓝背景
          },
        },
        fpsLimit: 60,
        particles: {
          color: {
            value: "#ffffff",
          },
          move: {
            direction: "none",
            enable: true,
            outModes: {
              default: "out",
            },
            random: false,
            speed: 0.5, // 星星缓慢移动
            straight: false,
          },
          number: {
            density: {
              enable: true,
              area: 800,
            },
            value: 100, // 星星数量
          },
          opacity: {
            value: 0.5,
            random: true,
            anim: {
              enable: true, // 开启闪烁
              speed: 1,
              opacity_min: 0.1,
              sync: false,
            },
          },
          shape: {
            type: "circle",
          },
          size: {
            value: { min: 1, max: 3 },
            random: true,
          },
        },
        detectRetina: true,
      }}
    />
  );
};

export default StarBackground;

