import './FloatingPlanets.css';

const FloatingPlanets = () => {
  return (
    <div className="floating-planets">
      {/* 蓝色行星 */}
      <div className="planet planet-1">
        <div className="planet-glow"></div>
        <div className="planet-surface"></div>
        <div className="planet-atmosphere"></div>
      </div>

      {/* 紫色行星 */}
      <div className="planet planet-2">
        <div className="planet-glow"></div>
        <div className="planet-surface"></div>
        <div className="planet-atmosphere"></div>
      </div>

      {/* 小蓝色行星 */}
      <div className="planet planet-3">
        <div className="planet-glow"></div>
        <div className="planet-surface"></div>
        <div className="planet-atmosphere"></div>
      </div>

      {/* 粉色行星 */}
      <div className="planet planet-4">
        <div className="planet-glow"></div>
        <div className="planet-surface"></div>
        <div className="planet-atmosphere"></div>
      </div>

      {/* 小紫色行星 */}
      <div className="planet planet-5">
        <div className="planet-glow"></div>
        <div className="planet-surface"></div>
        <div className="planet-atmosphere"></div>
      </div>
    </div>
  );
};

export default FloatingPlanets;

