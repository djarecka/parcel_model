"""Cloud Parcel Model based on Nenes et al, 2001; implemented by 
Daniel Rothenberg (darothen@mit.edu) as part of research undertaken for the
General examination in the Program in Atmospheres, Oceans, and Climate TEST"""

__docformat__ = 'reStructuredText'
import pandas
from lognorm import Lognorm, MultiModeLognorm

from pylab import *
ion()

from scipy.optimize import fsolve
from scipy.integrate import odeint

from parcel_aux import der, guesses
from micro import Seq, es, rho_w, Mw, sigma_w, R, kohler_crit

class AerosolSpecies(object):
    """This class organizes metadata about an aerosol species"""
    
    def __init__(self, **values):
        self.species = values['species'] # Species molecular formula
        self.kappa = values['kappa'] # Kappa hygroscopicity parameter
        
        self.distribution = values['distribution']
        self.r_drys = values['r_drys']
        self.Nis = values['Nis']
        self.nr = len(self.r_drys)
        self.rs = values['rs']
        
    def __repr__(self):
        return "%s - %r" % (self.species, self.distribution)

class ParcelModel(object):
    """This class wraps logic for initializing and running the Nenes et al, 2001
    cloud parcel model
    
    The model here is implemented in order to give an object-oriented approach to
    running the model. Instead of hard-coding aerosol size distributions and parcel
    initial conditions, the user can independently setup these parameters and pass
    them to the model to calculate everything necessary for running the model.
    
    :ivar aerosols: 
    :ivar V: Parcel updraft velocity (m/s)
    :ivar T0: Parcel initial temperature (K)
    :ivar S0: Parcel initial supersaturation, relative to 100% RH 
    :ivar P0: Parcel initial pressure (Pa)        
    """
    
    def __init__(self, aerosols, V, T0, S0, P0, console=False):
        """
        Initialize the model with information about updraft speed and the aerosol
        distribution. 
        """
        self.aerosols = aerosols
        self.V = V
        self.T0 = T0
        self.S0 = S0
        self.P0 = P0
        
        self.console = console
        
    def _setup_run(self, P0, T0, S0, make_plot=False):
        """
        Setup the initial parcel state for the run, given the initial
        temperature (K), pressure (Pa), and supersaturation, as well as
        the number of bins in which to divide the aerosol distribution.        
        """        
        out = dict()
        
        ## 1) Setup aerosols
        # a) grab all the initial aerosol size/concentrations
        species = []
        r_drys, Nis, kappas = [], [], []
        for aerosol in self.aerosols:
            r_drys.extend(aerosol.r_drys)
            kappas.extend([aerosol.kappa]*aerosol.nr)
            Nis.extend(aerosol.Nis)
            species.extend([aerosol.species]*aerosol.nr)
        
        r_drys = np.array(r_drys)
        kappas = np.array(kappas)
        Nis = np.array(Nis)
        
        out['r_drys'] = r_drys
        out['kappas'] = kappas
        out['Nis'] = Nis
        
        if self.console:
            print "AEROSOL DISTRIBUTION"
            print "%8s %6s" % ("r", "N")
            for sp, r, N in zip(species, r_drys, Nis):
                print "%10s %2.2e %4.1f" % (sp, r, N)
            print "\n"+"-"*44
            
        ## 2) Setup parcel initial conditions
        # a) water vapor
        wv0 = (1.-S0)*0.622*es(T0-273.15)/(P0-es(T0-273.15)) # Water Vapor mixing ratio, kg/kg
        
        # b) find equilibrium wet particle radius
        if self.console: print "calculating seeds for equilibrium solver..."
        r_guesses = np.array(guesses(T0, S0, r_drys, kappas))
        #r_guesses = []
        #for aerosol in self.aerosols:
        #    r_guesses.extend(guesses(T0, S0, r_drys, kappas))
        #r_guesses = np.array(r_guesses)
        if self.console: print " done"
                            
        # wrapper function for quickly computing deviation from chosen equilibrium supersaturation given
        # current size and dry size
        f = lambda r, r_dry, kappa: (Seq(r, r_dry, T0, kappa) - S0)
        ## Compute the equilibrium wet particle radii
        r0s = np.array([fsolve(f, (rd+guess)/2., args=(rd, kappa), xtol=1e-10)[0] for guess, rd, kappa in zip(r_guesses, r_drys, kappas)])
        ## Console logging output, if requested, of the equilibrium calcuations. Useful for 
        ## checking if the computations worked
        if self.console: 
            for (r,  r_dry, sp, kappa) in zip(r0s, r_drys, species, kappas):
                ss = Seq(r, r_dry, T0, kappa)
                rc, _ = kohler_crit(T0, r_dry, kappa)
                if r < 0 or r > 1e-3: print "Found bad r", r, r_dry, sp
                if np.abs(ss-S0)/S0 > 0.02: print "Found S discrepancy", ss, r_dry
        out['r0s'] = r0s

        # c) compute equilibrium droplet water content
        wc0 = np.sum([(4.*np.pi/3.)*rho_w*Ni*(r0**3 - r_dry**3) for r0, r_dry, Ni in zip(r0s, r_drys, Nis)])
        
        # d) concat into initial conditions arrays
        y0 = [P0, T0, wv0, wc0, S0]
        if self.console:
            print "PARCEL INITIAL CONDITIONS"
            print "    {:>8} {:>8} {:>8} {:>8} {:>8}".format("P (hPa)", "T (K)", "wv", "wc", "S")
            print "      %4.1f   %3.2f  %3.1e   %3.1e   %01.2f" % (P0/100., T0, wv0, wc0, S0)
        y0.extend(r0s)
        y0 = np.array(y0)
        out['y0'] = y0
        self.y0 = y0
        
        return out
        
    def run(self, P0, T0, S0, z_top, dt=0.1, max_steps=1000):
        
        setup_results = self._setup_run(P0, T0, S0)
        y0 = setup_results['y0']
        r_drys = setup_results['r_drys']
        kappas = setup_results['kappas']
        Nis = setup_results['Nis']
        nr = len(r_drys)
        
        aerosol = self.aerosols[0]
        
        ## Setup run time conditions        
        t0 = 0.
        if self.V:
            t_end = z_top/self.V
        else:
            t_end = dt*1000
        t = np.arange(t0, t_end+dt, dt)
        if self.console:
            print "\n"+"n_steps = %d" % (len(t))+"\n"
            raw_input("Continue run?")
        
        ## Setup integrator
        if self.console:
            x, info = odeint(der, y0, t, args=(nr, r_drys, Nis, self.V, kappas),
                             full_output=1, printmessg=1, ixpr=1, mxstep=max_steps,
                             mxhnil=0, atol=1e-15, rtol=1e-12)
        else:
            x = odeint(der, y0, t, args=(nr, r_drys, Nis, self.V, kappas),
                       mxstep=max_steps, mxhnil=0, atol=1e-15, rtol=1e-12)
    
        heights = t*self.V
        offset = 0
        if len(heights) > x.shape[0]:
            offset = 1
        
        df1 = pandas.DataFrame( {'P':x[:,0], 'T':x[:,1], 'wv':x[:,2],
                                'wc':x[:,3], 'S':x[:,4]} , index=heights[offset:])
        
        aerosol_dfs = {}
        species_shift = 0 # increment by nr to select the next aerosol's radii
        for aerosol in self.aerosols:
            nr = aerosol.nr
            species = aerosol.species
            
            labels = ["r%03d" % i for i in xrange(nr)]
            radii_dict = dict()
            for i, label in enumerate(labels):
                radii_dict[label] = x[:,5+species_shift+i]
                
            aerosol_dfs[species] = pandas.DataFrame( radii_dict, index=heights[offset:])
            species_shift += nr
        
        
        return df1, pandas.Panel(aerosol_dfs)

if __name__ == "__main__":
    
    ## Initial conditions
    P0 = 95000. # Pressure, Pa
    T0 = 285.2 # Temperature, K
    S0 = -0.05 # Supersaturation. 1-RH from wv term
    V = 0.5 # m/s
    
    ## Aerosol properties
    ## AEROSOL 1 - (NH4)2SO4
    # Chemistry
    ammonium_sulfate = { 
        'kappa': 0.6, # Hygroscopicity parameter
    }

    # Size Distribution
    mu, sigma, N, bins = 0.05, 2.0, 300., 200
    l = 0
    r = bins
    ## SINGLE MODE
    aerosol_dist = Lognorm(mu=mu, sigma=sigma, N=N)
    ## MULTIMODE
    #aerosol_dist = MultiModeLognorm(mus=[0.007, 0.027, 0.43],
    #                                sigmas=[1.8, 2.16, 2.21], 
    #                                Ns=[106000., 32000., 54.,])
    #mu = (multiply.reduce(aerosol_dist.mus))**(1./3.)
    #sigma = 6.0
    #############
    #lr, rr = np.log10(8e-4), np.log10(0.8) 
    lr, rr = np.log10(mu/(10.*sigma)), np.log10(mu*10.*sigma)
    
    rs = np.logspace(lr, rr, num=bins+1)[:]
    mids = np.array([np.sqrt(a*b) for a, b in zip(rs[:-1], rs[1:])])[l:r]
    Nis = np.array([0.5*(b-a)*(aerosol_dist.pdf(a) + aerosol_dist.pdf(b)) for a, b in zip(rs[:-1], rs[1:])])[l:r]
    r_drys = mids*1e-6
    
    ammonium_sulfate['distribution'] = aerosol_dist
    ammonium_sulfate['r_drys'] = r_drys
    ammonium_sulfate['rs'] = rs
    ammonium_sulfate['Nis'] = Nis*1e6
    ammonium_sulfate['species'] = '(NH4)2SO4'
    ammonium_sulfate['nr'] = len(r_drys)
    
    ## AEROSOL 2 - NaCl
    # Chemistry
    NaCl = { 'kappa': 0.01, # Hygroscopicity parameter
    }

    # Size Distribution
    '''
    mu, sigma, N, bins = 0.01, 1.35, 300., 200
    l = 0
    r = bins
    aerosol_dist = Lognorm(mu=mu, sigma=sigma, N=N)
    lr, rr = np.log10(mu/(10.*sigma)), np.log10(mu*10.*sigma)
    #lr, rr = np.log10(0.001), np.log10(3500.)
    rs = np.logspace(lr, rr, num=bins+1)[:]
    mids = np.array([np.sqrt(a*b) for a, b in zip(rs[:-1], rs[1:])])[l:r]
    Nis = np.array([0.5*(b-a)*(aerosol_dist.pdf(a) + aerosol_dist.pdf(b)) for a, b in zip(rs[:-1], rs[1:])])[l:r]
    r_drys = mids*1e-6
    '''
    r_drys = np.array([0.25*1e-6, ])
    rs = np.array([r_drys[0]*0.9, r_drys[0]*1.1])*1e6
    Nis = np.array([10000., ])
    
    
    NaCl['distribution'] = aerosol_dist
    NaCl['r_drys'] = r_drys
    NaCl['rs'] = rs
    NaCl['Nis'] = Nis*1e6
    NaCl['species'] = 'NaCl'
    NaCl['nr'] = len(r_drys)
    
    ######
    
    #initial_aerosols = [AerosolSpecies(**ammonium_sulfate), AerosolSpecies(**NaCl)]
    #initial_aerosols = [AerosolSpecies(**ammonium_sulfate)]
    #initial_aerosols = [AerosolSpecies(**NaCl)]
    initial_aerosols = [AerosolSpecies(**ammonium_sulfate), AerosolSpecies(**NaCl)]
    print initial_aerosols
    
    aer_species = [a.species for a in initial_aerosols]
    aer_dict = dict()
    for aerosol in initial_aerosols:
        aer_dict[aerosol.species] = aerosol
    
    for aerosol in initial_aerosols: print np.sum(aerosol.Nis) *1e-6
    
    figure(2, figsize=(12,10))
    #clf()
    subplot(3,2,1)
    colors = 'bgrcmyk'
    for i, aerosol in enumerate(initial_aerosols):
        rs, Nis = aerosol.rs, aerosol.Nis
        bar(rs[:-1], Nis/np.diff(rs)*1e-6, diff(rs), color=colors[i], alpha=0.5)
    #semilogy()
    #vlines(mids, 0, ylim()[1], color='red', linestyle='dotted')
    semilogx()
        
        
    pm = ParcelModel(initial_aerosols, V, T0, S0, P0, console=True)
    
    ## Run model    
    #rdt = np.max([V/100., 0.01])
    dt = 0.01
    parcel, aerosols = pm.run(P0, T0, S0, z_top=100.0, 
                              dt=dt, max_steps=500)
    
    xs = np.arange(501)
    parcel = parcel.ix[parcel.index % 1 == 0]
    aero_subset = {}
    for key in aerosols:
        print key
        aerosol = aerosols[key]
        subset = aerosol.ix[aerosol.index % 1 == 0]
        aero_subset[key] = subset
    aerosols = pandas.Panel(aero_subset)
    
    
    subplot(3,2,4)
    p = parcel.S.plot(logx=False)
    print parcel.S.max()
    max_idx = np.argmax(parcel.S)
    max_z = parcel.index[max_idx]
    vlines([max_z], ylim()[0], ylim()[1], color='k', linestyle='dashed')
    xlabel("Height"); ylabel("Supersaturation")
    
    #subplot(3,2,2)
    #step = 1 if len(aerosols) < 20000 else 50
    #for r in aerosols[::step]:
    #    (aerosols[r]*1e6).plot(logy=True)
    #vlines([max_z], ylim()[0], ylim()[1], color='k', linestyle='dashed')
    #xlabel("Height"); ylabel("Wet Radius, micron")
        
    
    subplot(3,2,3)
    plot(parcel['T'], parcel['P']*1e-2)
    ylim(ylim()[::-1])
    hlines([parcel.P[max_idx]*1e-2], xlim()[0], xlim()[1], color='k', linestyle='dashed')
    xlabel("Temperature"); ylabel("Pressure (hPa)")
    
    ## PLOT AEROSOLS!!
    show()
    n_species = len(aer_species)
    fig = figure(1, figsize=(9, 5*n_species))
    clf()
    for n, key in enumerate(aerosols):
        subplot(2, n_species, n+1)
        aerosol = aerosols[key]
        for r in aerosol:
            (aerosol[r]*1e6).plot(logy=True)
        vlines([max_z], ylim()[0], ylim()[1], color='k', linestyle='dashed')
        xlabel("Height"); ylabel("Wet Radius, micron")
        title(key)
    
        subplot(2, n_species, n+1 + n_species)
        initial_aerosol = initial_aerosols[n]
        rs, Nis = initial_aerosol.rs, initial_aerosol.Nis
        bar(rs[:-1], Nis, diff(rs), color=colors[n], alpha=0.2)
        
        rs, Nis = aerosol.ix[-1]*1e6, initial_aerosol.Nis
        if not rs.shape == Nis.shape:
            new_Nis = np.zeros_like(rs)
            new_Nis[:len(Nis)] = Nis[:]
            new_Nis[len(Nis):] = 0.0
            Nis = new_Nis
        plot(rs, Nis, color='k', alpha=0.5)
        semilogx(); #semilogy()
        
        rs, Nis = aerosol.ix[0]*1e6, initial_aerosol.Nis
        if not rs.shape == Nis.shape:
            new_Nis = np.zeros_like(rs)
            new_Nis[:len(Nis)] = Nis[:]
            new_Nis[len(Nis):] = 0.0
            Nis = new_Nis
        plot(rs, Nis, color='r', alpha=0.5)
        
        #rs, Nis = pm.y0[-initial_aerosol.nr:]*1e6, initial_aerosol.Nis
        #plot(rs, Nis, color='b', alpha=0.5)


    raw_input("N analysis...")

    for species in aer_species:
        print species
        aerosol = aerosols[species]
        aer_meta = aer_dict[species]
        Nis = aer_meta.Nis

        Neq = []
        Nkn = []
        Nunact = []    
        S_max = S0
    
        for S, T, i in zip(parcel.S, parcel['T'], xrange(len(parcel.S))):
    
            r_crits, s_crits = zip(*[kohler_crit(T, r_dry, aer_meta.kappa) for r_dry in aer_meta.r_drys])
            s_crits = np.array(s_crits)
            r_crits = np.array(r_crits)
            if S > S_max: S_max = S
    
            big_s =  S_max >= s_crits
            Neq.append(np.sum(Nis[big_s]))
    
            rstep = np.array(aerosol.ix[i])
            #active_radii = (S > s_crits) | (rstep > r_crits)
            active_radii = (rstep > r_crits)
            #sar = np.min(active_radii) if len(active_radii) > 0 else 1e99
            if len(active_radii) > 0:
                Nkn.append(np.sum(Nis[active_radii]))
                Nunact.append(np.sum(Nis[(rstep < r_crits)]))
            else:
                Nkn.append(0.0)           
                Nunact.append(np.sum(Nis))
            
            print parcel.index[i], Neq[i], Nkn[i], Nunact[i], S_max, S
    
        Neq = np.array(Neq)
        Nkn = np.array(Nkn)
        Nunact = np.array(Nunact)
    
        parcel[species+'_Neq'] = Neq
        parcel[species+'_Nkn'] = Nkn
        parcel[species+'_Nunact'] = Nunact
        
        alphaz = Nkn/Neq
        alphaz[isnan(alphaz)] = 0.
        phiz = Nunact/Nkn
        phiz[phiz == inf] = 1.
        
        parcel[species+'_alpha'] = alphaz
        parcel[species+'_phi'] = phiz
        
        figure(2)
        ax = subplot(3,2,5)
        parcel[[species+'_Neq', species+'_Nkn']].plot(ax=ax, grid=True)
        xlabel("Height")
        
        subplot(3,2,6)
        parcel[species+'_alpha'].plot()
        parcel[species+'_phi'].plot()
        ylim(0, 1)
        xlabel("Height"); ylabel(r'$\alpha(z),\quad\phi(z)$')
        print alphaz[-1]
        
        print "=="*35
        print species + " Summary - "
        print "Max activated fraction"
        print "   Eq: ", Neq.max()/np.sum(aer_meta.Nis)
        print "  Kin: ", Nkn.max()/np.sum(aer_meta.Nis)
        print ""
        print "Alpha maximum: %2.2f" % alphaz.max()
        print "  Phi maximum: %2.2f" % phiz.max()
        print "=="*35
