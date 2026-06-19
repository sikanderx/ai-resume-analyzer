import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Gem } from './gem';

describe('Gem', () => {
  let component: Gem;
  let fixture: ComponentFixture<Gem>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Gem],
    }).compileComponents();

    fixture = TestBed.createComponent(Gem);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
