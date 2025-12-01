import { useEffect, useRef } from 'react';
import './StarfieldBackground.css';

const StarfieldBackground = () => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let stars = [];
    let shootingStars = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      initStars();
    };

    class Star {
      constructor() {
        this.reset();
      }

      reset() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.z = Math.random() * 3;
        this.radius = 0.5 + Math.random() * 1.5;
        this.opacity = Math.random();
        this.twinkleSpeed = 0.001 + Math.random() * 0.003;
        this.twinkleDirection = Math.random() > 0.5 ? 1 : -1;
      }

      update() {
        this.opacity += this.twinkleSpeed * this.twinkleDirection;
        
        if (this.opacity <= 0 || this.opacity >= 1) {
          this.twinkleDirection *= -1;
        }
      }

      draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        
        const gradient = ctx.createRadialGradient(
          this.x, this.y, 0,
          this.x, this.y, this.radius * 3
        );
        
        const color = this.z > 2 ? '147, 197, 253' : this.z > 1 ? '196, 181, 253' : '255, 255, 255';
        
        gradient.addColorStop(0, `rgba(${color}, ${this.opacity})`);
        gradient.addColorStop(0.5, `rgba(${color}, ${this.opacity * 0.5})`);
        gradient.addColorStop(1, `rgba(${color}, 0)`);
        
        ctx.fillStyle = gradient;
        ctx.fill();
      }
    }

    class ShootingStar {
      constructor() {
        this.reset();
      }

      reset() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height * 0.5;
        this.length = 80 + Math.random() * 100;
        this.speed = 8 + Math.random() * 12;
        this.opacity = 1;
        this.angle = Math.PI / 4 + (Math.random() - 0.5) * 0.5;
      }

      update() {
        this.x += Math.cos(this.angle) * this.speed;
        this.y += Math.sin(this.angle) * this.speed;
        this.opacity -= 0.01;

        if (this.opacity <= 0 || this.x > canvas.width + 100 || this.y > canvas.height + 100) {
          this.reset();
        }
      }

      draw() {
        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(this.angle);

        const gradient = ctx.createLinearGradient(0, 0, -this.length, 0);
        gradient.addColorStop(0, `rgba(255, 255, 255, ${this.opacity})`);
        gradient.addColorStop(0.3, `rgba(147, 197, 253, ${this.opacity * 0.6})`);
        gradient.addColorStop(1, 'rgba(147, 197, 253, 0)');

        ctx.strokeStyle = gradient;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(-this.length, 0);
        ctx.stroke();

        ctx.restore();
      }
    }

    const initStars = () => {
      stars = [];
      const starCount = Math.floor((canvas.width * canvas.height) / 3000);
      for (let i = 0; i < starCount; i++) {
        stars.push(new Star());
      }
      
      shootingStars = [];
      for (let i = 0; i < 3; i++) {
        shootingStars.push(new ShootingStar());
      }
    };

    const drawConstellations = () => {
      ctx.strokeStyle = 'rgba(147, 197, 253, 0.15)';
      ctx.lineWidth = 1;
      
      for (let i = 0; i < stars.length; i++) {
        for (let j = i + 1; j < stars.length; j++) {
          const dx = stars[i].x - stars[j].x;
          const dy = stars[i].y - stars[j].y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 150 && Math.random() > 0.99) {
            ctx.beginPath();
            ctx.moveTo(stars[i].x, stars[i].y);
            ctx.lineTo(stars[j].x, stars[j].y);
            ctx.stroke();
          }
        }
      }
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // 绘制星座连线（偶尔）
      if (Math.random() > 0.95) {
        drawConstellations();
      }

      // 绘制并更新星星
      stars.forEach(star => {
        star.update();
        star.draw();
      });

      // 绘制并更新流星
      shootingStars.forEach(star => {
        star.update();
        star.draw();
      });

      animationFrameId = requestAnimationFrame(animate);
    };

    resize();
    window.addEventListener('resize', resize);
    animate();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return <canvas ref={canvasRef} className="starfield-background" />;
};

export default StarfieldBackground;

