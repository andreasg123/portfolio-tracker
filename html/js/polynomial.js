export class Polynomial {
  constructor(elements) {
    this.elements = elements || [];
  }

  append(el) {
    for (const el2 of this.elements) {
      if (el2[1] === el[1]) {
        el2[0] += el[0];
        return;
      }
    }
    this.elements.push(el)
  }

  clear() {
    this.elements.length = 0;
  }

  compute(x) {
    return this.elements.reduce(
      (sum, el) => sum + el[0] * (el[1] === 0 ? 1 : el[1] === 1 ? x : Math.pow(x, el[1])), 0);
  }

  solve() {
    if (this.elements.length === 2) {
      const e1 = this.elements[1][1];
      const f0 = this.elements[0][0];
      if (e1 === 0 && f0 !== 0) {
        // The current value (exponent==0) is added at the end.
        const factor = -this.elements[1][0] / f0;
        const e0 = this.elements[0][1];
        return factor < 0 ? -Math.pow(-factor, 1 / e0) : Math.pow(factor, 1 / e0);
      }
    }
    const deriv = this.derivative();
    let new_x = 1;
    let iter = 0;
    while (true) {
      iter++;
      const old_x = new_x;
      const dx = deriv.compute(old_x);
      if (dx == 0)
        return 0;
      const old_val = this.compute(old_x);
      new_x = old_x - old_val / dx;
      if (!isFinite(new_x) || Math.abs(new_x - old_x) < 1e-10 || iter >= 200) {
        if (!isFinite(new_x)) {
          console.log(new_x, old_x, old_val, dx);
        }
        break;
      }
    }
    return new_x;
  }

  derivative() {
    return new Polynomial(this.elements
                           .filter(el => el[1] > 0)
                           .map(el => [el[0] * el[1], el[1] - 1]));
  }
}

export function testPolynomial() {
  const p = new Polynomial();
  // 20% interest
  // $3 for two years
  // $2 for one year
  // 3 * 1.2 * 1.2 + 2 * 1.2 = 6.72
  p.append([3, 2]);
  p.append([2, 1]);
  p.append([-6.72, 0]);
  console.log(p.solve());
  console.log(p.compute(1.2));
}
