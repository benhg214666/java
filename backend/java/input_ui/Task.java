public class Task {
    private int r;
    private int p;
    private int e;
    private int d;
    private int w;
    private int preempt;

    public Task(int r, int p, int e, int d, int w, int preempt) {
        this.r = r;
        this.p = p;
        this.e = e;
        this.d = d;
        this.w = w;
        this.preempt = preempt;
    }

    public int getR() {
        return r;
    }

    public int getP() {
        return p;
    }

    public int getE() {
        return e;
    }

    public int getD() {
        return d;
    }

    public int getW() {
        return w;
    }

    public int getPreempt() {
        return preempt;
    }
}
