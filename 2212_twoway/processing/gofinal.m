pkg load signal
graphics_toolkit('gnuplot')  % beware of steps with fltk !
affiche=0;
fs=5e6;
Nint=1;

if (exist('args')==1)
  filename=args{1}
  dirlistmat=filename;
else
  dirlistmat=dir('./*mat');
  filename=dirlistmat(1).name
end

for dirnummat=1:length(dirlistmat)
  datename=str2num(filename(end-13:end-4))+10; % 10 seconds before the emission starts
  clear code
  filename
  eval(['load ',filename])
  solution1=indice1+correction1_a;
  OP=strfind(filename,"OP"); 
  if (isempty(OP)==1) OP=0;end
  if (OP==0)
    solution2=indice2+correction2_a;                          % reference channel
  end
  k=find(10*log10(SNR1i+SNR1r)>max(10*log10(SNR1i+SNR1r))-6); % arbitrarily keep max(SNR)-6 to remove initial record when TX inactive
  solution1=solution1(k);
  SNR1r=SNR1r(k);
  SNR1i=SNR1i(k);
  df1=df1(k);
  if (OP==0)
    solution2=solution2(k);
    SNR2r=SNR2r(k);
    SNR2i=SNR2i(k);
    df2=df2(k);
    solution=(solution1-solution2);  % time difference between reference and measurement
  else
    solution=(solution1);            % arbitrary reference time
  end
  [a,b]=polyfit([1:length(solution)],(solution)/(2*Nint+1)/fs,2);
  codelen(dirnummat)=length(code)/2;
  if (affiche==1)
    figure
    subplot(221)
    plot((solution)/(2*Nint+1)/fs); % ranging solution
    xlabel('time (s)')
    ylabel('ranging delay (s)')
    subplot(223)
    plot((solution)/(2*Nint+1)/fs-b.yf); % ranging solution
    legend(num2str(std((solution)/(2*Nint+1)/fs-b.yf)))
    xlabel('time (s)')
    ylabel('delay - parabolic fit (s)')
    subplot(222);plot(10*log10(SNR1r+SNR1i)(k))
    if (OP==0)
      subplot(224);plot(10*log10(SNR2r+SNR2i)(k))
    end
  end
  standard(dirnummat)=std((solution)/(2*Nint+1)/fs-b.yf);
  average(dirnummat)=mean((solution)/(2*Nint+1)/fs-b.yf);
  printf("%% y  m  d  h  m  s\tdelay\t\tdf1\tSNR1\tdf2\tSNR2\r\n");
  for p=1:length(SNR1i)
     % datestr(datenum([1970, 1, 1, 0, 0, 1670074201]))
     if (OP==0)
        printf("%s\t%.12f\t%.3f\t%.1f\t%.1f\t%.1f\n",strftime("%Y %m %d %H %M %S", localtime(datename+p*(length(code)/2)/2.5e6)),solution(p)/(2*Nint+1)/fs,df1(p),10*log10(SNR1i(p)+SNR1r(p)),df2(p),10*log10(SNR2i(p)+SNR2r(p)));
     else
        printf("%s\t%.12f\t%.3f\t%.1f\n",strftime("%Y %m %d %H %M %S", localtime(datename+p*(length(code)/2)/2.5e6)),solution(p)/(2*Nint+1)/fs,df1(p),10*log10(SNR1i(p)+SNR1r(p)));
     end
  end
end
[c,i]=sort(codelen);

if (length(standard>1))
  figure
  semilogx(c,standard(i)*1e9,'x-')
  xlabel('code length (bits)')
  ylabel('std(ranging) (ns)')
  hold on
end
